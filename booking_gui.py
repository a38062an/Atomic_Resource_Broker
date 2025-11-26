import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import argparse
import sys

# Import our modules
import reservation_api
import mock_reservation_api
from config_manager import ConfigManager
from booking_service import BookingService

class BookingSystemV2:
    def __init__(self, root: tk.Tk, booking_service: BookingService):
        self.root = root
        self.service = booking_service
        self.root.title("Atomic Resource Broker - Booking System")
        self.root.geometry("1000x700")
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' usually looks cleaner than default
        
        # Main Layout
        self.create_layout()
        
        # Redirect stdout
        self.stdout_original = sys.stdout
        sys.stdout = self.StdoutRedirector(self.log_area)
        
        # Initial Data Load
        self.root.after(100, self.refresh_status)

    def create_layout(self):
        # Top Header / Goal Explanation
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)
        
        title_label = ttk.Label(header_frame, text="Atomic Resource Broker", font=("Helvetica", 18, "bold"))
        title_label.pack(side=tk.TOP, anchor=tk.W)
        
        goal_text = "GOAL: Secure matching time slots for both Hotel and Band services.\n" \
                    "The system ensures atomic transactions: you either get both slots or neither."
        goal_label = ttk.Label(header_frame, text=goal_text, font=("Helvetica", 12), foreground="#555")
        goal_label.pack(side=tk.TOP, anchor=tk.W, pady=(5, 0))

        # Main Content Area (Split into Left Control Panel and Right Status/Log)
        content_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Left Panel: Controls ---
        left_panel = ttk.Frame(content_frame)
        content_frame.add(left_panel, weight=1)
        
        # Action Group: Automated Booking (The Main Action)
        auto_frame = ttk.LabelFrame(left_panel, text="Automated Booking", padding="10")
        auto_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(auto_frame, text="Find & Reserve Earliest Matching Slot", command=self.reserve_earliest, state="normal").pack(fill=tk.X, pady=2)
        ttk.Label(auto_frame, text="Automatically finds the first available slot common to both services.", font=("Arial", 10, "italic"), foreground="#666").pack(anchor=tk.W)

        # Action Group: Manual Actions
        manual_frame = ttk.LabelFrame(left_panel, text="Manual Operations", padding="10")
        manual_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(manual_frame, text="View Available Slots", command=self.show_available_slots).pack(fill=tk.X, pady=2)
        
        # Grid for manual booking buttons
        btn_grid = ttk.Frame(manual_frame)
        btn_grid.pack(fill=tk.X, pady=2)
        ttk.Button(btn_grid, text="Book Hotel Only", command=lambda: self.book_specific('hotel')).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        ttk.Button(btn_grid, text="Book Band Only", command=lambda: self.book_specific('band')).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        
        ttk.Button(manual_frame, text="Book Specific Slot (Both)", command=lambda: self.book_specific(None)).pack(fill=tk.X, pady=2)

        # Action Group: Cleanup & Cancellation
        cancel_frame = ttk.LabelFrame(left_panel, text="Cleanup & Cancellation", padding="10")
        cancel_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(cancel_frame, text="Cancel Unneeded (Keep Earliest Pair)", command=self.cancel_unneeded).pack(fill=tk.X, pady=2)
        ttk.Button(cancel_frame, text="CANCEL ALL RESERVATIONS", command=self.cancel_all).pack(fill=tk.X, pady=2)

        # --- Right Panel: Status & Logs ---
        right_panel = ttk.Frame(content_frame)
        content_frame.add(right_panel, weight=2)
        
        # Status Dashboard
        status_frame = ttk.LabelFrame(right_panel, text="Current Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label_hotel = ttk.Label(status_frame, text="Hotel Slots Held: Checking...", font=("Consolas", 11))
        self.status_label_hotel.pack(anchor=tk.W)
        
        self.status_label_band = ttk.Label(status_frame, text="Band Slots Held:  Checking...", font=("Consolas", 11))
        self.status_label_band.pack(anchor=tk.W)
        
        self.status_label_match = ttk.Label(status_frame, text="Matches Secured:  None", font=("Consolas", 11, "bold"), foreground="red")
        self.status_label_match.pack(anchor=tk.W, pady=(5,0))
        
        ttk.Button(status_frame, text="Refresh Status", command=self.refresh_status).pack(anchor=tk.E, pady=(5,0))

        # Log Area
        log_frame = ttk.LabelFrame(right_panel, text="Activity Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    # --- Logic Integration ---

    def run_async(self, task_func, callback=None):
        """Helper to run tasks in a separate thread"""
        def wrapper():
            result = task_func()
            if callback:
                self.root.after(0, lambda: callback(result))
            else:
                self.root.after(0, self.refresh_status) # Default to refreshing status
        
        threading.Thread(target=wrapper, daemon=True).start()

    def refresh_status(self):
        def get_status():
            return self.service.viewCurrentSlots()
        
        def update_ui(result):
            held_hotel, held_band = result
            hotel_ids = sorted([int(s['id']) for s in held_hotel if s])
            band_ids = sorted([int(s['id']) for s in held_band if s])
            matches = sorted(list(set(hotel_ids) & set(band_ids)))
            
            self.status_label_hotel.config(text=f"Hotel Slots Held: {hotel_ids if hotel_ids else 'None'}")
            self.status_label_band.config(text=f"Band Slots Held:  {band_ids if band_ids else 'None'}")
            
            if matches:
                self.status_label_match.config(text=f"Matches Secured:  {matches}", foreground="green")
            else:
                self.status_label_match.config(text=f"Matches Secured:  None", foreground="red")

        self.run_async(get_status, update_ui)

    def reserve_earliest(self):
        print("\n--- Starting Automated Reservation ---")
        self.run_async(self.service.reserveEarliestSlot)

    def show_available_slots(self):
        print("\n--- Checking Availability ---")
        def task():
            return self.service.viewFirst20FreeSlots()
        
        def callback(slots):
            print("Available Hotel:", slots.get('hotel', []))
            print("Available Band: ", slots.get('band', []))
            
            # Find matches in available
            h_set = set(slots.get('hotel', []))
            b_set = set(slots.get('band', []))
            matches = sorted(list(h_set & b_set))
            print(f"Potential Matches: {matches[:5]}")

        self.run_async(task, callback)

    def book_specific(self, service_type):
        # Simple dialog for input
        dialog = tk.Toplevel(self.root)
        dialog.title("Book Slot")
        dialog.geometry("300x150")
        
        ttk.Label(dialog, text="Enter Slot Number:").pack(pady=10)
        entry = ttk.Entry(dialog)
        entry.pack(pady=5)
        entry.focus()
        
        def confirm():
            try:
                num = int(entry.get())
                dialog.destroy()
                print(f"\n--- Manual Booking: Slot {num} ({service_type if service_type else 'Both'}) ---")
                self.run_async(lambda: self.service.reserveSlot(num, service_type))
            except ValueError:
                messagebox.showerror("Error", "Invalid number")
        
        ttk.Button(dialog, text="Book", command=confirm).pack(pady=10)

    def cancel_unneeded(self):
        print("\n--- Cleaning Up Unneeded Slots ---")
        self.run_async(self.service.cancelAllUnmatchedSlots)

    def cancel_all(self):
        print("\n--- CANCELLING ALL RESERVATIONS ---")
        self.run_async(self.service.cancelAllSlots)

    # Stdout Redirector Class
    class StdoutRedirector:
        def __init__(self, text_widget):
            self.text_widget = text_widget

        def write(self, string):
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, string)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)

        def flush(self):
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Run in demo mode')
    args = parser.parse_args()

    config_mgr = ConfigManager()
    
    if args.demo:
        print("Running in DEMO mode")
        ApiClass = mock_reservation_api.MockReservationApi
    else:
        ApiClass = reservation_api.ReservationApi

    h_conf = config_mgr.get_hotel_config()
    b_conf = config_mgr.get_band_config()
    g_conf = config_mgr.get_global_config()

    hotel_api = ApiClass(h_conf['url'], h_conf['key'], int(g_conf['retries']), float(g_conf['delay']))
    band_api = ApiClass(b_conf['url'], b_conf['key'], int(g_conf['retries']), float(g_conf['delay']))

    service = BookingService(hotel_api, band_api)

    root = tk.Tk()
    app = BookingSystemV2(root, service)
    root.mainloop()