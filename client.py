import socket
import threading
import time
import logging
from protocol import (
    TYPE_SUBSCRIBE, TYPE_NOTIFY, TYPE_ACK,
    encode_packet, decode_packet
)

# Configuration
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("UDP_Client")

class NotificationClient:
    def __init__(self, server_host=SERVER_IP, server_port=SERVER_PORT, loss_rate=0.0, verbose=True):
        self.server_addr = (server_host, server_port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # We don't bind to a specific port, OS will assign one.
        self.received_seqs = set() # Track for duplicate detection
        self.running = True
        self.loss_rate = loss_rate
        self.delivery_count = 0
        self.latencies = []
        self.verbose = verbose

    def subscribe(self):
        """Send a SUBSCRIBE message to the server."""
        logger.info(f"Subscribing to server at {self.server_addr}...")
        packet = encode_packet(0, TYPE_SUBSCRIBE, "")
        self.send_with_loss(packet, self.server_addr)

    def send_with_loss(self, packet, addr):
        """Send packet with simulated loss."""
        import random
        if random.random() < self.loss_rate:
            logger.warning(f"Simulated DROP ACK/SUBSCRIBE to {addr}")
            return
        self.client_socket.sendto(packet, addr)

    def listen(self):
        """Listen for notifications from the server."""
        while self.running:
            try:
                data, addr = self.client_socket.recvfrom(4096)
                seq_num, msg_type, payload, is_valid = decode_packet(data)

                if not is_valid:
                    logger.warning("Invalid packet received.")
                    continue

                if msg_type == TYPE_NOTIFY:
                    self.received_at = time.time()
                    self.handle_notification(seq_num, payload, addr)
                else:
                    logger.debug(f"Received non-notification message type {msg_type}")
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

    def handle_notification(self, seq_num, message, addr):
        """Process notification and send ACK."""
        # Send ACK first (always ACK duplicates because the previous ACK might have been lost)
        logger.info(f"Received notification {seq_num}: '{message}'. Sending ACK...")
        ack_packet = encode_packet(seq_num, TYPE_ACK, "")
        self.send_with_loss(ack_packet, self.server_addr)

        # Duplicate detection
        if seq_num in self.received_seqs:
            logger.info(f"Duplicate packet {seq_num} ignored.")
            return

        self.received_seqs.add(seq_num)
        self.delivery_count += 1
        # In a real test, we would compare with send time. For now just record receipt.
        if self.verbose:
            print(f"\n>>> NOTIFICATION [{seq_num}]: {message}\n")

    def start(self):
        """Start the client listener thread."""
        self.subscribe()
        listener_thread = threading.Thread(target=self.listen, daemon=True)
        listener_thread.start()
        
        try:
            while self.running:
                # Keep main thread alive
                msg = input()
                if msg.lower() == 'quit':
                    self.running = False
        except KeyboardInterrupt:
            self.running = False

if __name__ == "__main__":
    client = NotificationClient()
    client.start()
