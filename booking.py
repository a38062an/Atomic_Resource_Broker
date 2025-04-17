#!/usr/bin/python3
import tkinter
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

# Your code goes here
# Helper functions

# Global variable to track last API request time
last_request_time = 0


def enforce_rate_limit():
    """Ensures at least 1 second has passed since the last API request"""
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

        # Debugging output
        print("hotel slots: held " + str(held_hotel))
        print("band slots held: " + str(held_band))

        return held_hotel, held_band
    except Exception as e:
        print("Error retrieving held slots: ", e)


def viewFirst5FreeSlots() -> list:
    try:
        enforce_rate_limit()
        available_hotel = hotel.get_slots_available()

        enforce_rate_limit()
        available_band = band.get_slots_available()

        # Debugging output
        print("Available hotel slots: " + str(available_hotel))
        print("Available band slots: " + str(available_band))

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

        # Debugging output
        print("Available hotel slots: " + str(available_hotel))
        print("Available band slots: " + str(available_band))

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

                print(
                    f"Earliest matching slot {earliest_slot_to_reserve} reserved in both hotel and band."
                )
            else:
                print(
                    f"Currently holding the earliest possible slot: {min(matching_slots_held)}"
                )
                break  # If the current slot is the earliest, stop searching

            # No need for additional sleep since enforce_rate_limit already handles this

        except Exception as e:
            print(f"Error reserving earliest slot: {e}")
            break  # Or handle retries if needed


def cancelSlot(num: int) -> None:
    try:
        enforce_rate_limit()
        response_hotel = hotel.release_slot(num)
        response_band = band.release_slot(num)
        print("Slot cancelled successfully: ", response_hotel)
        print("Slot cancelled successfully: ", response_band)
    except Exception as e:
        print("Error cancelling slot: ", e)


def cancelUneededSlots() -> None:
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


