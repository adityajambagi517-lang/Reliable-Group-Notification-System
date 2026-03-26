import socket
import threading
import time
import logging
from protocol import (
    TYPE_SUBSCRIBE, TYPE_NOTIFY, TYPE_ACK,
    encode_packet, decode_packet
)

# Configuration
SERVER_IP = "0.0.0.0"
SERVER_PORT = 5000
TIMEOUT = 2.0  # seconds
MAX_RETRIES = 3

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("UDP_Server")

class NotificationServer:
    def __init__(self, host=SERVER_IP, port=SERVER_PORT, loss_rate=0.0):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((host, port))
        self.subscribers = set()  # Set of (addr, port)
        self.pending_acks = {}    # (seq_num, addr) -> {data, retries, timestamp}
        self.next_seq_num = 1
        self.lock = threading.Lock()
        self.running = True
        self.loss_rate = loss_rate
        self.retransmission_count = 0

    def listen(self):
        """Main loop to receive packets."""
        logger.info(f"Server started on {SERVER_IP}:{SERVER_PORT}")
        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(4096)
                seq_num, msg_type, payload, is_valid = decode_packet(data)

                if not is_valid:
                    logger.warning(f"Invalid packet received from {addr}")
                    continue

                if msg_type == TYPE_SUBSCRIBE:
                    self.handle_subscribe(addr)
                elif msg_type == TYPE_ACK:
                    self.handle_ack(seq_num, addr)
                else:
                    logger.warning(f"Unknown message type {msg_type} from {addr}")
            except ConnectionResetError:
                # Windows UDP quirk: ignore ICMP port unreachable
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error in listen loop: {e}")
                continue

            except Exception as e:
                if self.running:
                    logger.error(f"Error in listen loop: {e}")

    def handle_subscribe(self, addr):
        """Add a client to the subscriber list."""
        with self.lock:
            if addr not in self.subscribers:
                self.subscribers.add(addr)
                logger.info(f"New subscriber: {addr}")
            # Send confirmation (as a notify or just ACK? The prompt says SUBSCRIBE message to register, doesn't specify ACK for subscription, but good practice.)
            # We'll just log it for now.

    def handle_ack(self, seq_num, addr):
        """Mark a notification as acknowledged by a client."""
        with self.lock:
            key = (seq_num, addr)
            if key in self.pending_acks:
                del self.pending_acks[key]
                logger.info(f"ACK received for seq {seq_num} from {addr}")

    def broadcast(self, message):
        """Send a notification to all subscribers reliably."""
        with self.lock:
            seq_num = self.next_seq_num
            self.next_seq_num += 1
            
            packet = encode_packet(seq_num, TYPE_NOTIFY, message)
            
            for addr in list(self.subscribers):
                logger.info(f"Sending notification {seq_num} to {addr}")
                self.send_with_loss(packet, addr)
                
                # Store in pending ACKs
                self.pending_acks[(seq_num, addr)] = {
                    'packet': packet,
                    'retries': 0,
                    'timestamp': time.time()
                }

    def send_with_loss(self, packet, addr):
        """Send packet with simulated loss."""
        import random
        if random.random() < self.loss_rate:
            logger.warning(f"Simulated DROP packet to {addr}")
            return
        self.server_socket.sendto(packet, addr)

    def retransmission_thread(self):
        """Background thread to handle timeouts and retries."""
        while self.running:
            time.sleep(0.5)  # Check every 0.5s
            now = time.time()
            with self.lock:
                to_retransmit = []
                to_drop = []
                
                for key, info in self.pending_acks.items():
                    if now - info['timestamp'] >= TIMEOUT:
                        if info['retries'] < MAX_RETRIES:
                            to_retransmit.append(key)
                        else:
                            to_drop.append(key)
                
                for key in to_retransmit:
                    seq_num, addr = key
                    info = self.pending_acks[key]
                    info['retries'] += 1
                    self.retransmission_count += 1
                    info['timestamp'] = now
                    logger.info(f"Retransmitting notification {seq_num} to {addr} (Try {info['retries']})")
                    self.send_with_loss(info['packet'], addr)
                
                for key in to_drop:
                    seq_num, addr = key
                    logger.error(f"Failed to deliver notification {seq_num} to {addr} after {MAX_RETRIES} retries. Removing subscriber.")
                    # self.subscribers.remove(addr) # Optional: remove flaky clients
                    del self.pending_acks[key]

    def start_input_loop(self):
        """Thread to allow manual notification triggers."""
        while self.running:
            msg = input("Enter notification message to send (or 'exit'): ")
            if msg.lower() == 'exit':
                self.running = False
                break
            self.broadcast(msg)

if __name__ == "__main__":
    server = NotificationServer()
    
    # Start threads
    listener = threading.Thread(target=server.listen, daemon=True)
    retrans = threading.Thread(target=server.retransmission_thread, daemon=True)
    
    listener.start()
    retrans.start()
    
    server.start_input_loop()
