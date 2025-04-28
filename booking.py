
# !/usr/bin/python3
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

# Create API objects to communicate with the hotel and band APIs
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

def viewFirst5FreeSlots() -> dict:
    """
    Retrieve the first 5 matching available slots for both hotel and band services,
    considering already held slots.
    Returns:
        A dictionary with a key 'matching', containing a list of up to 5 matching available slots.
    """
    try:
        enforce_rate_limit()
        available_hotel = hotel.get_slots_available()
        enforce_rate_limit()
        available_band = band.get_slots_available()

        enforce_rate_limit()
        held_hotel = hotel.get_slots_held()
        enforce_rate_limit()
        held_band = band.get_slots_held()

        # Convert slot IDs to sets
        available_hotel_slots = {int(slot['id']) for slot in available_hotel}
        available_band_slots = {int(slot['id']) for slot in available_band}
        held_hotel_slots = {int(slot['id']) for slot in held_hotel}
        held_band_slots = {int(slot['id']) for slot in held_band}

        # Find the intersection of available slots
        matching_slots = available_hotel_slots & available_band_slots

        # Include held slots that match available slots
        matching_slots.update(held_hotel_slots & available_band_slots)
        matching_slots.update(held_band_slots & available_hotel_slots)

        # Return the first 5 matching slots
        return {"matching": sorted(matching_slots)[:5]}
    except Exception as e:
        print("Error retrieving matching available slots: ", e)
        return {"matching": []}


def viewFirst20FreeSlots() -> dict:

    """
    Retrieve the first 20 available slots for both hotel and band services.
    Returns:
        A dictionary with keys 'hotel' and 'band', each containing a list of up to 20 available slots.
    """
    try:
        enforce_rate_limit()
        available_hotel = hotel.get_slots_available()

        enforce_rate_limit()
        available_band = band.get_slots_available()

        # Get the first 20 slots for each service
        hotel_slots = sorted([slot['id'] for slot in available_hotel], key=int)[:20]
        band_slots = sorted([slot['id'] for slot in available_band], key=int)[:20]

        return {"hotel": hotel_slots, "band": band_slots}
    except Exception as e:
        print("Error retrieving available slots: ", e)
        return {"hotel": [], "band": []}


def reserveSlot(num: int, service_type=None) -> (dict, dict):
    """
    Reserve a slot for either hotel, band, or both.

    Args:
        num: The slot number to reserve
        service_type: 'hotel', 'band', or None (for both)

    Returns:
        Tuple of (hotel_response, band_response) - may contain empty dictionaries if service not requested
    """
    hotel_reserved = False
    band_reserved = False
    hotel_response = {}
    band_response = {}

    try:
        # Reserve hotel if requested
        if service_type is None or service_type == 'hotel':
            enforce_rate_limit()
            hotel_response = hotel.reserve_slot(num)
            hotel_reserved = True
            print(f"Slot {num} for hotel reserved successfully")

        # Reserve band if requested
        if service_type is None or service_type == 'band':
            enforce_rate_limit()
            band_response = band.reserve_slot(num)
            band_reserved = True
            print(f"Slot {num} for band reserved successfully")

        return hotel_response, band_response

    except Exception as e:
        print(f"Error reserving slot {num}: {e}")

        # Rollback logic: Cancel any successful reservation if the other fails and both were requested
        if service_type is None:  # Only need rollback if trying to book both
            if hotel_reserved and not band_reserved:
                try:
                    print(f"Rolling back hotel reservation for slot {num}...")
                    enforce_rate_limit()
                    hotel.release_slot(num)
                    print(f"Successfully rolled back hotel slot {num}")
                except Exception as rollback_error:
                    print(f"WARNING: Failed to roll back hotel slot {num}: {rollback_error}")

            elif band_reserved and not hotel_reserved:
                try:
                    print(f"Rolling back band reservation for slot {num}...")
                    enforce_rate_limit()
                    band.release_slot(num)
                    print(f"Successfully rolled back band slot {num}")
                except Exception as rollback_error:
                    print(f"WARNING: Failed to roll back band slot {num}: {rollback_error}")

        return hotel_response, band_response

def reserveEarliestSlot():
    """
    Reserves the earliest matching pair of slots (hotel and band).
    Handles reservation limits by cleaning up unmatched slots first.
    """
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        try:
            # First, let's see what slots we already have
            enforce_rate_limit()
            held_hotel, held_band = viewCurrentSlots()

            # Create sets of held slot IDs
            hotel_slots_held = {int(slot['id']) for slot in held_hotel if slot is not None}
            band_slots_held = {int(slot['id']) for slot in held_band if slot is not None}

            # Find matching pairs we already have
            matching_slots_held = hotel_slots_held & band_slots_held

            # Find unmatched slots
            unmatched_hotel = hotel_slots_held - band_slots_held
            unmatched_band = band_slots_held - hotel_slots_held

            # Check if we need to clean up due to reservation limits
            if len(hotel_slots_held) >= 2 or len(band_slots_held) >= 2:
                print("Potential reservation limit issue detected. Cleaning up unmatched slots first...")

                # Cancel unmatched hotel slots to free up reservation capacity
                for slot_id in unmatched_hotel:
                    print(f"Cancelling unmatched hotel slot {slot_id} to free up capacity")
                    enforce_rate_limit()
                    hotel.release_slot(slot_id)

                # Cancel unmatched band slots to free up reservation capacity
                for slot_id in unmatched_band:
                    print(f"Cancelling unmatched band slot {slot_id} to free up capacity")
                    enforce_rate_limit()
                    band.release_slot(slot_id)

                # Refresh our slot data after cancellations
                enforce_rate_limit()
                held_hotel, held_band = viewCurrentSlots()
                hotel_slots_held = {int(slot['id']) for slot in held_hotel if slot is not None}
                band_slots_held = {int(slot['id']) for slot in held_band if slot is not None}
                matching_slots_held = hotel_slots_held & band_slots_held

            # Get available matching slots
            enforce_rate_limit()
            earliest_slots = viewFirst5FreeSlots().get("matching", [])

            if not earliest_slots:
                print("No matching slots currently available.")
                return False

            # Get the earliest slot number
            earliest_slot_to_reserve = earliest_slots[0]
            print(f"Found earliest matching slot: {earliest_slot_to_reserve}")

            # If we already have matching pairs, check if the new one is earlier
            if matching_slots_held:
                earliest_held = min(matching_slots_held)
                if earliest_slot_to_reserve >= earliest_held:
                    print(f"Already holding the earliest matching slot at {earliest_held}")
                    return True
                else:
                    print(f"Found earlier matching slot {earliest_slot_to_reserve} than current {earliest_held}")
                    # Cancel the current matching pair to free up capacity
                    print(f"Cancelling current matching pair at slot {earliest_held} to free up capacity")
                    enforce_rate_limit()
                    cancelSlot(earliest_held)

            # Determine what needs to be reserved
            need_hotel = earliest_slot_to_reserve not in hotel_slots_held
            need_band = earliest_slot_to_reserve not in band_slots_held

            # Track what was newly reserved in this attempt
            newly_reserved_hotel = False
            newly_reserved_band = False

            # Reserve only what's needed
            if need_hotel and need_band:
                print(f"Attempting to reserve both hotel and band for slot {earliest_slot_to_reserve}")
                enforce_rate_limit()
                hotel_response, band_response = reserveSlot(earliest_slot_to_reserve)
                newly_reserved_hotel = bool(hotel_response)
                newly_reserved_band = bool(band_response)
            elif need_hotel:
                print(f"Band slot {earliest_slot_to_reserve} already held, reserving hotel only")
                enforce_rate_limit()
                hotel_response, _ = reserveSlot(earliest_slot_to_reserve, 'hotel')
                newly_reserved_hotel = bool(hotel_response)
                band_response = True  # Already held
            elif need_band:
                print(f"Hotel slot {earliest_slot_to_reserve} already held, reserving band only")
                enforce_rate_limit()
                _, band_response = reserveSlot(earliest_slot_to_reserve, 'band')
                newly_reserved_band = bool(band_response)
                hotel_response = True  # Already held
            else:
                print(f"Slot {earliest_slot_to_reserve} status is inconsistent")
                hotel_response = band_response = False

            # Check if reservation was successful
            if hotel_response and band_response:
                print(f"Successfully reserved matching pair for slot {earliest_slot_to_reserve}")

                # Clean up any remaining unmatched slots
                enforce_rate_limit()
                cancel_all_unmatched_slots()
                return True
            else:
                # Rollback any partial reservation we just made
                if newly_reserved_hotel and not band_response:
                    print(f"Rolling back hotel reservation for slot {earliest_slot_to_reserve}")
                    enforce_rate_limit()
                    hotel.release_slot(earliest_slot_to_reserve)

                if newly_reserved_band and not hotel_response:
                    print(f"Rolling back band reservation for slot {earliest_slot_to_reserve}")
                    enforce_rate_limit()
                    band.release_slot(earliest_slot_to_reserve)

                print(f"Failed to reserve complete matching pair for slot {earliest_slot_to_reserve}")
                attempt += 1
                if attempt < max_attempts:
                    print(f"Retrying... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(1)

        except Exception as e:
            print(f"Error in reserveEarliestSlot: {e}")
            attempt += 1
            if attempt < max_attempts:
                print(f"Retrying... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(2)

    print("Failed to reserve earliest slot after multiple attempts.")
    return False


def cancel_all_unmatched_slots():
    """
    Cancel all slots that don't have a matching pair
    """
    try:
        held_hotel, held_band = viewCurrentSlots()

        # Get all slot IDs
        hotel_slots = {int(slot['id']) for slot in held_hotel if slot is not None}
        band_slots = {int(slot['id']) for slot in held_band if slot is not None}

        # Find matching pairs (slots held in both hotel and band)
        matching_slots = hotel_slots & band_slots

        # Find slots that only exist in one service but not the other
        unmatched_hotel = hotel_slots - band_slots
        unmatched_band = band_slots - hotel_slots

        # Cancel unmatched hotel slots
        for slot_id in unmatched_hotel:
            print(f"Cancelling unmatched hotel slot {slot_id}")
            enforce_rate_limit()
            hotel.release_slot(slot_id)

        # Cancel unmatched band slots
        for slot_id in unmatched_band:
            print(f"Cancelling unmatched band slot {slot_id}")
            enforce_rate_limit()
            band.release_slot(slot_id)

        print("Unmatched slots cleanup completed")

    except Exception as e:
        print(f"Error cancelling unmatched slots: {e}")

def cancelSlot(num: int, service_type=None):
    """
    Cancel a slot for either hotel, band, or both.

    Args:
        num: The slot number to cancel
        service_type: 'hotel', 'band', or None (for both)

    Returns:
        True if cancelled successfully, False otherwise
    """
    hotel_cancelled = False
    band_cancelled = False

    try:
        # Cancel hotel if requested
        if service_type is None or service_type == 'hotel':
            enforce_rate_limit()
            hotel.release_slot(num)
            hotel_cancelled = True
            print(f"Hotel slot {num} cancelled successfully")

        # Cancel band if requested
        if service_type is None or service_type == 'band':
            enforce_rate_limit()
            band.release_slot(num)
            band_cancelled = True
            print(f"Band slot {num} cancelled successfully")

        if (service_type is None and hotel_cancelled and band_cancelled) or \
                (service_type == 'hotel' and hotel_cancelled) or \
                (service_type == 'band' and band_cancelled):
            return True

        return False

    except Exception as e:
        print(f"Error cancelling slot {num}: {e}")

        # Rollback logic - if one cancellation succeeded but the other failed when cancelling both
        if service_type is None:
            if hotel_cancelled and not band_cancelled:
                try:
                    print(f"Attempting to restore hotel slot {num} (rollback)...")
                    enforce_rate_limit()
                    hotel.reserve_slot(num)
                    print(f"Successfully restored hotel slot {num}")
                except Exception as rollback_error:
                    print(f"WARNING: Failed to restore hotel slot {num}: {rollback_error}")
                    print(f"System may be in inconsistent state for slot {num}")

            elif band_cancelled and not hotel_cancelled:
                try:
                    print(f"Attempting to restore band slot {num} (rollback)...")
                    enforce_rate_limit()
                    band.reserve_slot(num)
                    print(f"Successfully restored band slot {num}")
                except Exception as rollback_error:
                    print(f"WARNING: Failed to restore band slot {num}: {rollback_error}")
                    print(f"System may be in inconsistent state for slot {num}")

        return False


def cancelAllSlots():
    """
    Cancels all currently held slots with error handling for individual slots
    """
    try:
        # Get current reservations
        held_hotel, held_band = viewCurrentSlots()
        hotel_slots = {slot['id'] for slot in held_hotel if slot is not None}
        band_slots = {slot['id'] for slot in held_band if slot is not None}

        # Track which slots failed to cancel
        failed_hotel_slots = []
        failed_band_slots = []

        # Cancel hotel slots with individual exception handling
        for slot in hotel_slots:
            try:
                enforce_rate_limit()
                hotel.release_slot(slot)
                print(f"Cancelled hotel slot {slot}")
            except Exception as e:
                print(f"Failed to cancel hotel slot {slot}: {e}")
                failed_hotel_slots.append(slot)

        # Cancel band slots with individual exception handling
        for slot in band_slots:
            try:
                enforce_rate_limit()
                band.release_slot(slot)
                print(f"Cancelled band slot {slot}")
            except Exception as e:
                print(f"Failed to cancel band slot {slot}: {e}")
                failed_band_slots.append(slot)

        # Report any failures
        if failed_hotel_slots or failed_band_slots:
            print(f"WARNING: Some slots could not be cancelled.")
            if failed_hotel_slots:
                print(f"Failed hotel slots: {failed_hotel_slots}")
            if failed_band_slots:
                print(f"Failed band slots: {failed_band_slots}")

    except Exception as e:
        print(f"Error in cancelAllSlots: {e}")


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
        # Define the buttons - updated to include independent booking options
        buttons = [
            ("View Current Bookings", self.showCurrentSlots),
            ("View First 20 Available Slots", self.showAvailableSlots),
            ("Book Hotel Slot", lambda: self.bookSpecificSlot('hotel')),
            ("Book Band Slot", lambda: self.bookSpecificSlot('band')),
            ("Book Both Hotel & Band Slot", lambda: self.bookSpecificSlot(None)),
            ("Cancel Hotel Booking", lambda: self.cancelBooking('hotel')),
            ("Cancel Band Booking", lambda: self.cancelBooking('band')),
            ("Cancel Both Hotel & Band Booking", lambda: self.cancelBooking(None)),
            ("View First 5 Matching Slots", self.ShowMatchingSlots),
            ("Reserve Earliest Matching Slot", self.reserveEarliest),
            ("Cancel Unneeded Reservations", self.cancelUnneededReservations),  # New button
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
        self.output_text.config(state=tk.DISABLED) # unmodifiable

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
            self.text_widget.config(state=tk.NORMAL)  # Temporarily enable editing
            self.text_widget.insert(tk.END, string)  # Insert the string
            self.text_widget.see(tk.END)  # Scroll to the end
            self.text_widget.config(state=tk.DISABLED)  # Disable editing again

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

        print(f"Hotel slots: {sorted(list(hotel_slots), key=int)}")
        print(f"Band slots: {sorted(list(band_slots), key=int)}")
        print(f"Matching slots (both hotel and band): {sorted(list(matching_slots), key=int)}")
        self.enableAllButtons()

    def showAvailableSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Retrieving available slots")

        def perform_task():
            available_slots = viewFirst20FreeSlots()
            self.root.after(0, lambda: self.displayAvailableSlotsResults(available_slots))

        threading.Thread(target=perform_task, daemon=True).start()

    def displayAvailableSlotsResults(self, available_slots: dict):
        self.stopLoading()
        self.clearOutput()
        print("First 20 available slots retrieved:")

        if available_slots:
            print("\nAvailable slots grouped by service:")
            for service, slots in available_slots.items():
                print(f"{service.capitalize()} slots:")
                for i, slot in enumerate(slots, 1):
                    print(f"  {i}. Slot {slot}")
        else:
            print("No available slots found.")
        self.enableAllButtons()

    def bookSpecificSlot(self, service_type=None):
        # Set the dialog title based on what's being booked
        if service_type == 'hotel':
            title = "Book Hotel Slot"
            label_text = "Enter slot number to book for hotel:"
        elif service_type == 'band':
            title = "Book Band Slot"
            label_text = "Enter slot number to book for band:"
        else:
            title = "Book Hotel & Band Slot"
            label_text = "Enter slot number to book for both hotel and band:"

        # Create a dialog to get slot number
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()  # Make dialog modal

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # Add label and entry
        tk.Label(dialog, text=label_text).pack(pady=(10, 0))
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

                if service_type == 'hotel':
                    message = f"Attempting to reserve hotel slot {slot_num}"
                elif service_type == 'band':
                    message = f"Attempting to reserve band slot {slot_num}"
                else:
                    message = f"Attempting to reserve hotel and band slot {slot_num}"

                self.startLoading(message)

                def perform_task():
                    response_hotel, response_band = reserveSlot(slot_num, service_type)
                    self.root.after(0, lambda: self.displayReserveResults(slot_num, service_type))

                threading.Thread(target=perform_task, daemon=True).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid slot number.")

        # Add buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Book", command=on_book, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def displayReserveResults(self, slot_num: int, service_type=None):
        self.stopLoading()
        if service_type == 'hotel':
            print(f"Completed hotel reservation attempt for slot {slot_num}")
        elif service_type == 'band':
            print(f"Completed band reservation attempt for slot {slot_num}")
        else:
            print(f"Completed hotel and band reservation attempt for slot {slot_num}")
        self.enableAllButtons()

    def cancelBooking(self, service_type=None):
        # Set the dialog title based on what's being cancelled
        if service_type == 'hotel':
            title = "Cancel Hotel Booking"
            label_text = "Enter slot number to cancel for hotel:"
        elif service_type == 'band':
            title = "Cancel Band Booking"
            label_text = "Enter slot number to cancel for band:"
        else:
            title = "Cancel Hotel & Band Booking"
            label_text = "Enter slot number to cancel for both hotel and band:"

        # Create a dialog to get slot number
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()  # Make dialog modal

        # Center the dialog
        dialog.geometry(f"+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # Add label and entry
        tk.Label(dialog, text=label_text).pack(pady=(10, 0))
        entry = tk.Entry(dialog, width=10)
        entry.pack(pady=10)
        entry.focus_set()

        def on_cancel():
            try:
                slot_num = int(entry.get())
                dialog.destroy()

                self.clearOutput()
                self.disableAllButtons()

                if service_type == 'hotel':
                    message = f"Attempting to cancel hotel slot {slot_num}"
                elif service_type == 'band':
                    message = f"Attempting to cancel band slot {slot_num}"
                else:
                    message = f"Attempting to cancel hotel and band slot {slot_num}"

                self.startLoading(message)

                def perform_task():
                    cancelSlot(slot_num, service_type)
                    self.root.after(0, lambda: self.displayCancelResults(slot_num, service_type))

                threading.Thread(target=perform_task, daemon=True).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid slot number.")

        # Add buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Cancel Booking", command=on_cancel, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Close", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def displayCancelResults(self, slot_num: int, service_type=None):
        self.stopLoading()
        if service_type == 'hotel':
            print(f"Completed hotel cancellation attempt for slot {slot_num}")
        elif service_type == 'band':
            print(f"Completed band cancellation attempt for slot {slot_num}")
        else:
            print(f"Completed hotel and band cancellation attempt for slot {slot_num}")
        self.enableAllButtons()

    def ShowMatchingSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Retrieving matching slots")

        def perform_task():
            matching_slots = viewFirst5FreeSlots()
            self.root.after(0, lambda: self.displayMatchingSlotsResults(matching_slots))

        threading.Thread(target=perform_task, daemon=True).start()

    def displayMatchingSlotsResults(self, matching_slots: dict):
        self.stopLoading()
        self.clearOutput()
        print("First 5 matching slots retrieved:")

        if matching_slots:
            print("\nMatching slots grouped by service:")
            for service, slots in matching_slots.items():
                print(f"{service.capitalize()} slots:")
                for i, slot in enumerate(slots, 1):
                    print(f"  {i}. Slot {slot}")
        else:
            print("No matching available slots found.")
        self.enableAllButtons()

    def reserveEarliest(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Finding and reserving earliest matching slot")

        def perform_task():
            reserveEarliestSlot()
            self.root.after(0, self.displayReserveEarliestResults)

        threading.Thread(target=perform_task, daemon=True).start()

    def displayReserveEarliestResults(self):
        self.stopLoading()
        print("Earliest matching slot reservation process completed")
        self.enableAllButtons()

    def cancelUnneededReservations(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Cancelling unneeded reservations")

        def perform_task():
            cancel_all_unmatched_slots()  # Use the existing function
            self.root.after(0, self.displayCancelUnneededResults)

        threading.Thread(target=perform_task, daemon=True).start()

    def displayCancelUnneededResults(self):
        self.stopLoading()
        print("Unneeded reservations have been cancelled")
        self.enableAllButtons()

    def cancelAllSlots(self):
        self.clearOutput()
        self.disableAllButtons()
        self.startLoading("Cancelling all reservations")

        def perform_task():
            cancelAllSlots()
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