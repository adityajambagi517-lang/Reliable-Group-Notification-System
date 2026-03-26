import time
import threading
import matplotlib.pyplot as plt
from server import NotificationServer
from client import NotificationClient

def run_test(loss_rate, port, num_clients=3, num_notifications=5):
    print(f"\n--- Running Test: Loss Rate = {loss_rate*100}% on port {port} ---")
    
    # Start server
    server = NotificationServer(port=port, loss_rate=loss_rate)
    server_thread = threading.Thread(target=server.listen, daemon=True)
    retrans_thread = threading.Thread(target=server.retransmission_thread, daemon=True)
    server_thread.start()
    retrans_thread.start()
    
    # Start clients
    clients = []
    for i in range(num_clients):
        client = NotificationClient(server_port=port, loss_rate=loss_rate, verbose=False)
        
        t = threading.Thread(target=client.listen, daemon=True)
        t.start()
        client.subscribe()
        clients.append(client)
    
    # Wait for all clients to be subscribed (since SUBSCRIBE can also be lost)
    print("Waiting for all clients to subscribe...")
    start_wait = time.time()
    while len(server.subscribers) < num_clients and time.time() - start_wait < 10:
        for c in clients:
            if len(server.subscribers) < num_clients:
                c.subscribe()
        time.sleep(1)
    
    if len(server.subscribers) < num_clients:
        print(f"Warning: Only {len(server.subscribers)}/{num_clients} clients subscribed.")
    else:
        print("All clients subscribed. Starting broadcast.")
    
    # Broadcast notifications
    for i in range(num_notifications):
        server.broadcast(f"Test message {i+1}")
        time.sleep(0.1)
    
    # Wait for all retransmissions to settle (max retry 3 * 2s = 6s + buffer)
    time.sleep(10)
    
    # Collect results
    total_expected = num_clients * num_notifications
    total_received = sum(len(c.received_seqs) for c in clients)
    delivery_rate = (total_received / total_expected) * 100
    retransmissions = server.retransmission_count
    
    print(f"Results for Loss Rate {loss_rate*100}%:")
    print(f"  Delivery Rate: {delivery_rate:.2f}%")
    print(f"  Retransmissions: {retransmissions}")
    
    # Cleanup
    server.running = False
    for c in clients:
        c.running = False
        c.client_socket.close()
    if server.server_socket:
        server.server_socket.close()
    
    return delivery_rate, retransmissions

if __name__ == "__main__":
    loss_rates = [0.0, 0.1, 0.2, 0.3]
    delivery_rates = []
    retrans_counts = []
    
    for i, lr in enumerate(loss_rates):
        port = 5000 + i
        dr, rc = run_test(lr, port)
        delivery_rates.append(dr)
        retrans_counts.append(rc)
    
    # Plotting
    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:blue'
    ax1.set_xlabel('Simulated Packet Loss Rate')
    ax1.set_ylabel('Delivery Rate (%)', color=color)
    ax1.plot(loss_rates, delivery_rates, marker='o', color=color, label='Delivery Rate')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_ylim(0, 105)

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Retransmission Count', color=color)
    ax2.bar(loss_rates, retrans_counts, alpha=0.3, color=color, width=0.05, label='Retransmissions')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Reliable UDP performance under Packet Loss')
    fig.tight_layout()
    plt.savefig('performance_results.png')
    print("\nTest completed. Results saved to 'performance_results.png'.")
