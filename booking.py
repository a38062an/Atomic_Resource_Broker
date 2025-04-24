#!/usr/bin/python3
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import reservationapi
import configparser
import time

# Load the configuration file containing the URLs and keys
config = configparser.ConfigParser()
config.read("api.ini")

# Create an API object to communicate with the hotel API
hotel = reservationapi.ReservationApi(config['hotel']['url'],
                                      config['hotel']['key'],
                                      int(config['global']['retries']),
                                      float(config['global']['delay']))

band = reservationapi.ReservationApi(config['band']['url'],
                                     config['band']['key'],
                                     int(config['global']['retries']),
                                     float(config['global']['delay']))

# Global variable to track last API request time
last_request_time = 0


def enforce_rate_limit():
    """
    Ensures at least 1 second has passed since the last API request
    Better to use this approach rather than calling time.sleep(1) in every function
    This is because time.sleep(1) might make us wait longer than necessary
    """

    global last_request_time
    current_time = time.time()
    elapsed = current_time - last_request_time

    # If less than 1 second has passed since the last request, sleep for the remaining time
    if elapsed < 1:
        time.sleep(1 - elapsed)

    # Update the last request time
    last_request_time = time.time()


# Functions to handle REQUIREMENTS
def viewCurrentSlots() -> (list, list):
    try:
        enforce_rate_limit()
        held_hotel = hotel.get_slots_held()
        enforce_rate_limit()
        held_band = band.get_slots_held()
        return held_hotel, held_band
    except Exception as e:
        print("Error retrieving held slots: ", e)
        return [], []


def viewFirst5FreeSlots() -> list:
    try:
        enforce_rate_limit()
        available_hotel = hotel.get_slots_available()

        enforce_rate_limit()
        available_band = band.get_slots_available()

        # Find the intersection of available slots in both hotel and band
        hotel_slots = {slot['id'] for slot in available_hotel}
        band_slots = {slot['id'] for slot in available_band}

        available_slots = hotel_slots & band_slots
        sorted_available_slots = sorted(available_slots)

        return sorted_available_slots[:5]
    except Exception as e:
        print("Error retrieving held slots: ", e)
        return []


def viewFirst20FreeSlots() -> list:
    try:
        enforce_rate_limit()
        available_hotel = hotel.get_slots_available()

        enforce_rate_limit()
        available_band = band.get_slots_available()

        # Find the intersection of available slots in both hotel and band
        hotel_slots = {slot['id'] for slot in available_hotel}
        band_slots = {slot['id'] for slot in available_band}

        available_slots = hotel_slots & band_slots
        sorted_available_slots = sorted(available_slots)

        return sorted_available_slots[:20]
    except Exception as e:
        print("Error retrieving held slots: ", e)
        return []

def reserveSlot(num: int) -> (dict, dict):
    hotel_reserved = False  # Flag to track hotel reservation status
    try:
        # First, check currently held slots to determine if this is a better slot
        held_hotel, held_band = viewCurrentSlots()
        hotel_slots_held = {int(slot['id']) for slot in held_hotel if slot is not None}
        band_slots_held = {int(slot['id']) for slot in held_band if slot is not None}
        matching_slots_held = hotel_slots_held & band_slots_held

        # If there are matching slots already held, only proceed if this slot is earlier
        if matching_slots_held and num >= min(matching_slots_held):
            print(
                f"Cannot reserve slot {num} as you already have a matching slot {min(matching_slots_held)} which is earlier or the same.")
            return {}, {}

        # Otherwise proceed with reservation
        enforce_rate_limit()
        response_hotel = hotel.reserve_slot(num)
        hotel_reserved = True  # Hotel reservation was successful

        enforce_rate_limit()
        response_band = band.reserve_slot(num)

        print("Slot reserved successfully: ", response_hotel)
        print("Slot reserved successfully: ", response_band)
        return response_hotel, response_band
    except Exception as e:
        print("Error reserving slot: ", e)
        # Rollback: Cancel the hotel reservation *only if it was successful*
        if hotel_reserved:
            try:
                enforce_rate_limit()
                hotel.release_slot(num)
                print(f"Cancelled hotel slot {num} due to band reservation failure.")
            except Exception as rollback_error:
                print(
                    f"Error cancelling hotel slot {num} during rollback: {rollback_error}"
                )
        return {}, {}


def reserveEarliestSlot():
    '''
    Reserves the earliest available matching slot, continuously checking for even earlier slots.

    1. Get the earliest 5 free slots
    2. Check if earliest available slot is available in both hotel and band
    3. Check if earliest available slot is earlier than current held slots
    4. Reserve the earliest available slot
    5. If no slots are available, print a message
    '''
    while True:  # Keep looping to find the earliest
        earliest_slots = viewFirst5FreeSlots()  # Get currently available matches
        if not earliest_slots:
            print("No matching slots currently available.")
            break  # Or potentially retry after a delay

        earliest_slot_to_reserve = earliest_slots[0]

        try:
            held_hotel, held_band = viewCurrentSlots()
            hotel_slots_held = {slot['id'] for slot in [slot for slot in held_hotel if slot is not None]}
            band_slots_held = {slot['id'] for slot in [slot for slot in held_band if slot is not None]}
            matching_slots_held = hotel_slots_held & band_slots_held

            # If no slots are held or the new slot is earlier than any held slots, reserve it.
            if (not matching_slots_held) or earliest_slot_to_reserve < min(matching_slots_held, default=float('inf')):
                # If there are slots held, cancel them.
                if matching_slots_held:
                    cancelUneededSlots()

                enforce_rate_limit()
                hotel_response = hotel.reserve_slot(earliest_slot_to_reserve)

                enforce_rate_limit()
                band_response = band.reserve_slot(earliest_slot_to_reserve)

                print(f"Earliest matching slot {earliest_slot_to_reserve} reserved in both hotel and band.")
            else:
                print(f"Currently holding the earliest possible slot: {min(matching_slots_held)}")
                break  # If the current slot is the earliest, stop searching

            # No need for additional sleep since enforce_rate_limit already handles this

        except Exception as e:
            print(f"Error reserving earliest slot: {e}")
            break  # Or handle retries if needed


def cancelSlot(num: int):
    try:
        enforce_rate_limit()
        response_hotel = hotel.release_slot(num)
        enforce_rate_limit()
        response_band = band.release_slot(num)
        print("Slot cancelled successfully: ", response_hotel)
        print("Slot cancelled successfully: ", response_band)
    except Exception as e:
        print("Error cancelling slot: ", e)


def cancelUneededSlots():
    """
    Cancels all currently held slots
    """
    try:
        held_hotel, held_band = viewCurrentSlots()
        hotel_slots = {slot['id'] for slot in [slot for slot in held_hotel if slot is not None]}
        band_slots = {slot['id'] for slot in [slot for slot in held_band if slot is not None]}

        for slot in hotel_slots:
            enforce_rate_limit()
            hotel.release_slot(slot)
            print(f"Cancelled hotel slot {slot} ")

        for slot in band_slots:
            enforce_rate_limit()
            band.release_slot(slot)
            print(f"Cancelled band slot {slot} ")

    except Exception as e:
        print(f"Error in cancelUneededSlots: {e}")


# GUI Class Definition
class BookingSystem:
    '''
    - The GUI uses multi-threading to ensure that the UI remains responsive while API calls are made.
    - The GUI is built using tkinter and consists of buttons for various actions and a text area for output.
    - The multi-threading works by having functions that handle loading animations and button states in the main thread,
    while the actual API calls are made in separate threads.
    - For each button action, the structure is as follows:
        1. Clear the output area.
        2. Disable all buttons to prevent further interaction.
        3. Start a loading animation.
        4. Create a new thread to perform the API call.
        5. Once the API call is complete, call a display results function.
        6. The display results function stops the loading animation and re-enables the buttons.
    '''

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Booking System")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Dictionary to store button references - Define this BEFORE createButtons
        self.buttons = {}

        # Status variable for loading animation
        self.loading = False
        self.loading_dots = 0
        self.loading_task = None

        # Create frame for the UI
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create frame for buttons
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Create frame for output
        self.output_frame = tk.Frame(self.main_frame)
        self.output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create buttons
        self.createButtons()

        # Create output text area
        self.createOutputArea()

        self.stdout_original = sys.stdout  # Store original stdout to restore later for good practise

        # Redirect standard output to text widget
        # stdout is looking for a write method, so we create a class that has this method that feeds into out output text area
        # Now all print() statements will be redirected to the text widget
        sys.stdout = self.StdoutRedirector(self.output_text)

        # Show current slots when app starts
        self.root.after(100, self.showCurrentSlots)

    def createButtons(self):
        buttons = [
            ("View Current Bookings", self.showCurrentSlots),
            ("View First 20 Available Slots", self.showAvailableSlots),
            ("Book a Specific Slot", self.bookSpecificSlot),
            ("Cancel a Booking", self.cancelBooking),
            ("View First 5 Matching Slots", self.ShowMatchingSlots),
            ("Reserve Earliest Slot", self.reserveEarliest),
            ("Cancel All Reservations", self.cancelAllSlots),
            ("Exit", self.exitApp)
        ]

        for text, command in buttons:
            btn = tk.Button(self.button_frame, text=text, command=command, width=25)
            btn.pack(pady=5, fill=tk.X)
            self.buttons[text] = btn

    def createOutputArea(self):
        # Create scrolled text widget for output
        self.output_text = scrolledtext.ScrolledText(self.output_frame, wrap=tk.WORD,
                                                     width=50, height=25)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.config(state=tk.NORMAL)

    def clearOutput(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.NORMAL)

    # Functions to start loading animation and continue it
    # Loading will stop when the API thread finishes and root.after is called
    def startLoading(self, message: str):
        """Start showing a loading animation"""
        self.loading = True
        self.loading_dots = 0
        self.updateLoadingAnimation(message)

    def updateLoadingAnimation(self, message: str):
        """Update the loading animation with dots"""
        if self.loading:
            self.clearOutput()
            dots = "." * self.loading_dots
            print(f"{message}{dots}")
            self.loading_dots = (self.loading_dots + 1) % 4
            self.loading_task = self.root.after(300, lambda: self.updateLoadingAnimation(message))

    def stopLoading(self):
        """Stop the loading animation"""
        if self.loading_task:
            self.root.after_cancel(self.loading_task)
        self.loading = False
        self.loading_task = None

    # During Loading disable all buttons
    # After Loading re-enable all buttons
    def disableAllButtons(self):
        """Disable all buttons while processing"""
        for btn in self.buttons.values():
            btn.config(state=tk.DISABLED)

    def enableAllButtons(self):
        for btn in self.buttons.values():
            btn.config(state=tk.NORMAL)

    # Function to handle stdout redirection
    class StdoutRedirector:
        def __init__(self, text_widget: scrolledtext.ScrolledText) -> None:
            self.text_widget = text_widget  # Initialized with text widget (scrolledtext)

        def write(self, string: str):
            self.text_widget.insert(tk.END, string)  # Insert string to text widget'
            self.text_widget.see(tk.END)  # Scroll to the end of the text widget'

        def flush(self):
            pass

    # Button command functions with threading
    def showCurrentSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Retrieving current held slots")

        def perform_task():
            held_hotel, held_band = viewCurrentSlots()
            self.root.after(0, lambda: self.displayCurrentSlotsResults(held_hotel, held_band))

        threading.Thread(target=perform_task, daemon=True).start()

    def displayCurrentSlotsResults(self, held_hotel: list, held_band: list):
        self.stopLoading()
        self.clearOutput()
        print("Current held slots retrieved:")

        # Additional user-friendly output
        print("\nSummary of held slots:")
        hotel_slots = {slot['id'] for slot in held_hotel if slot is not None}
        band_slots = {slot['id'] for slot in held_band if slot is not None}
        matching_slots = hotel_slots & band_slots

        print(f"Hotel slots: {sorted(list(hotel_slots))}")
        print(f"Band slots: {sorted(list(band_slots))}")
        print(f"Matching slots (both hotel and band): {sorted(list(matching_slots))}")
        self.enableAllButtons()

    def showAvailableSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Retrieving available slots")

        def perform_task():
            available_slots = viewFirst20FreeSlots()
            self.root.after(0, lambda: self.displayAvailableSlotsResults(available_slots))

        threading.Thread(target=perform_task, daemon=True).start()

    def displayAvailableSlotsResults(self, available_slots: list):
        self.stopLoading()
        self.clearOutput()
        print("First 20 available slots retrieved:")

        if available_slots:
            print("\nAvailable matching slots (first 20):")
            for i, slot in enumerate(available_slots, 1):
                print(f"{i}. Slot {slot}")
        else:
            print("No matching available slots found.")
        self.enableAllButtons()

    def bookSpecificSlot(self):
        # Create a dialog to get slot number
        dialog = tk.Toplevel(self.root)
        dialog.title("Book Specific Slot")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()  # Make dialog modal

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # Add label and entry
        tk.Label(dialog, text="Enter slot number to book:").pack(pady=(10, 0))
        entry = tk.Entry(dialog, width=10)
        entry.pack(pady=10)
        entry.focus_set()

        # Function to handle booking once the mini GUI shows up
        def on_book():
            try:
                slot_num = int(entry.get())
                dialog.destroy()

                self.clearOutput()
                self.disableAllButtons()
                self.startLoading(f"Attempting to reserve slot {slot_num}")

                def perform_task():
                    response_hotel, response_band = reserveSlot(slot_num)
                    self.root.after(0, lambda: self.displayReserveResults(slot_num))

                threading.Thread(target=perform_task, daemon=True).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid slot number.")

        # Add buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Book", command=on_book, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def displayReserveResults(self, slot_num: int):
        self.stopLoading()
        print(f"Completed reservation attempt for slot {slot_num}")
        self.enableAllButtons()

    def cancelBooking(self):
        # Create a dialog to get slot number
        dialog = tk.Toplevel(self.root)
        dialog.title("Cancel a Booking")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()  # Make dialog modal

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # Add label and entry
        tk.Label(dialog, text="Enter slot number to cancel:").pack(pady=(10, 0))
        entry = tk.Entry(dialog, width=10)
        entry.pack(pady=10)
        entry.focus_set()

        def on_cancel():
            try:
                slot_num = int(entry.get())
                dialog.destroy()

                self.clearOutput()
                self.disableAllButtons()
                self.startLoading(f"Attempting to cancel slot {slot_num}")

                def perform_task():
                    cancelSlot(slot_num)
                    self.root.after(0, lambda: self.displayCancelResults(slot_num))

                threading.Thread(target=perform_task, daemon=True).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid slot number.")

        # Add buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Cancel Booking", command=on_cancel, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Close", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def displayCancelResults(self, slot_num: int):
        self.stopLoading()
        print(f"Completed cancellation attempt for slot {slot_num}")
        self.enableAllButtons()

    def ShowMatchingSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Retrieving matching slots")

        def perform_task():
            matching_slots = viewFirst5FreeSlots()
            self.root.after(0, lambda: self.displayMatchingSlotsResults(matching_slots))

        threading.Thread(target=perform_task, daemon=True).start()

    def displayMatchingSlotsResults(self, matching_slots: list):
        self.stopLoading()
        self.clearOutput()
        print("First 5 matching slots retrieved:")

        if matching_slots:
            print("\nFirst 5 matching available slots:")
            for i, slot in enumerate(matching_slots, 1):
                print(f"{i}. Slot {slot}")
        else:
            print("No matching available slots found.")
        self.enableAllButtons()

    def reserveEarliest(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Finding and reserving earliest slot")

        def perform_task():
            reserveEarliestSlot()
            self.root.after(0, self.displayReserveEarliestResults)

        threading.Thread(target=perform_task, daemon=True).start()

    def displayReserveEarliestResults(self):
        self.stopLoading()
        print("Earliest slot reservation process completed")
        self.enableAllButtons()

    def cancelAllSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Cancelling all reservations")

        def perform_task():
            cancelUneededSlots()
            self.root.after(0, self.displayCancelAllResults)

        threading.Thread(target=perform_task, daemon=True).start()

    def displayCancelAllResults(self):
        self.stopLoading()
        print("All reservations have been cancelled")
        self.enableAllButtons()

    def exitApp(self):
        # Restore original stdout
        sys.stdout = self.stdout_original

        # Ask for confirmation before exit
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            self.root.destroy()


# Main function to run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = BookingSystem(root)
    root.protocol("WM_DELETE_WINDOW", app.exitApp)  # Handle window close button
    root.mainloop()
