import time

class BookingService:
    """
    Handles all the logic for finding and booking slots.
    Keeps the UI code clean by doing the heavy lifting here.
    """
    def __init__(self, hotel_api, band_api):
        self.hotel = hotel_api
        self.band = band_api
        self.last_request_time = 0

    def enforce_rate_limit(self):
        """
        Ensures at least 1 second has passed since the last API request
        Better to use this approach rather than calling time.sleep(1) in every function
        This is because time.sleep(1) might make us wait longer than necessary
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        # If less than 1 second has passed since the last request, sleep for the remaining time
        if elapsed < 1:
            time.sleep(1 - elapsed)

        # Update the last request time
        self.last_request_time = time.time()

    def viewCurrentSlots(self) -> (list, list):
        try:
            self.enforce_rate_limit()
            held_hotel = self.hotel.get_slots_held()
            self.enforce_rate_limit()
            held_band = self.band.get_slots_held()
            return held_hotel, held_band
        except Exception as e:
            print("Error retrieving held slots: ", e)
            return [], []

    def viewFirst5FreeSlots(self) -> dict:
        """
        Retrieve the first 5 matching available slots for both hotel and band services,
        considering already held slots.
        """
        try:
            self.enforce_rate_limit()
            available_hotel = self.hotel.get_slots_available()
            self.enforce_rate_limit()
            available_band = self.band.get_slots_available()

            self.enforce_rate_limit()
            held_hotel = self.hotel.get_slots_held()
            self.enforce_rate_limit()
            held_band = self.band.get_slots_held()

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

    def viewFirst20FreeSlots(self) -> dict:
        """
        Retrieve the first 20 available slots for both hotel and band services.
        """
        try:
            self.enforce_rate_limit()
            available_hotel = self.hotel.get_slots_available()

            self.enforce_rate_limit()
            available_band = self.band.get_slots_available()

            # Get the first 20 slots for each service
            hotel_slots = sorted([slot['id'] for slot in available_hotel], key=int)[:20]
            band_slots = sorted([slot['id'] for slot in available_band], key=int)[:20]

            return {"hotel": hotel_slots, "band": band_slots}
        except Exception as e:
            print("Error retrieving available slots: ", e)
            return {"hotel": [], "band": []}

    def reserveSlot(self, num: int, service_type=None) -> (dict, dict):
        """
        Reserve a slot for either hotel, band, or both.
        """
        hotel_reserved = False
        band_reserved = False
        hotel_response = {}
        band_response = {}

        try:
            # Reserve hotel if requested
            if service_type is None or service_type == 'hotel':
                self.enforce_rate_limit()
                hotel_response = self.hotel.reserve_slot(num)
                hotel_reserved = True
                print(f"Slot {num} for hotel reserved successfully")

            # Reserve band if requested
            if service_type is None or service_type == 'band':
                self.enforce_rate_limit()
                band_response = self.band.reserve_slot(num)
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
                        self.enforce_rate_limit()
                        self.hotel.release_slot(num)
                        print(f"Successfully rolled back hotel slot {num}")
                    except Exception as rollback_error:
                        print(f"WARNING: Failed to roll back hotel slot {num}: {rollback_error}")

                elif band_reserved and not hotel_reserved:
                    try:
                        print(f"Rolling back band reservation for slot {num}...")
                        self.enforce_rate_limit()
                        self.band.release_slot(num)
                        print(f"Successfully rolled back band slot {num}")
                    except Exception as rollback_error:
                        print(f"WARNING: Failed to roll back band slot {num}: {rollback_error}")

            return hotel_response, band_response

    def cancelSlot(self, num: int, service_type=None):
        """
        Cancel a slot for either hotel, band, or both.
        """
        hotel_cancelled = False
        band_cancelled = False

        try:
            # Cancel hotel if requested
            if service_type is None or service_type == 'hotel':
                self.enforce_rate_limit()
                self.hotel.release_slot(num)
                hotel_cancelled = True
                print(f"Hotel slot {num} cancelled successfully")

            # Cancel band if requested
            if service_type is None or service_type == 'band':
                self.enforce_rate_limit()
                self.band.release_slot(num)
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
                        self.enforce_rate_limit()
                        self.hotel.reserve_slot(num)
                        print(f"Successfully restored hotel slot {num}")
                    except Exception as rollback_error:
                        print(f"WARNING: Failed to restore hotel slot {num}: {rollback_error}")
                        print(f"System may be in inconsistent state for slot {num}")

                elif band_cancelled and not hotel_cancelled:
                    try:
                        print(f"Attempting to restore band slot {num} (rollback)...")
                        self.enforce_rate_limit()
                        self.band.reserve_slot(num)
                        print(f"Successfully restored band slot {num}")
                    except Exception as rollback_error:
                        print(f"WARNING: Failed to restore band slot {num}: {rollback_error}")
                        print(f"System may be in inconsistent state for slot {num}")

            return False

    def cancelAllUnmatchedSlots(self):
        """
        Cancel all slots that don't have a matching pair and also cancel any matching pairs
        that are later than the earliest matching pair
        Function for removing uneeded reservation there are three cases below
        """
        try:
            held_hotel, held_band = self.viewCurrentSlots()

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
                self.enforce_rate_limit()
                self.hotel.release_slot(slot_id)

            # Cancel unmatched band slots
            for slot_id in unmatched_band:
                print(f"Cancelling unmatched band slot {slot_id}")
                self.enforce_rate_limit()
                self.band.release_slot(slot_id)

            # If we have more than one matching pair, keep only the earliest one
            if len(matching_slots) > 1:
                # Find the earliest matching slot
                earliest_slot = min(matching_slots)

                # Cancel all other matching slots (keep only the earliest)
                slots_to_cancel = matching_slots - {earliest_slot}

                for slot_id in slots_to_cancel:
                    print(f"Cancelling later matching pair at slot {slot_id}")
                    self.enforce_rate_limit()
                    self.hotel.release_slot(slot_id)
                    self.enforce_rate_limit()
                    self.band.release_slot(slot_id)

                print(f"Kept earliest matching pair at slot {earliest_slot}")

            print("Unmatched slots cleanup completed")

        except Exception as e:
            print(f"Error cancelling unmatched slots: {e}")

    def cancelAllSlots(self):
        """
        Cancels all currently held slots with error handling for individual slots
        """
        try:
            # Get current reservations
            held_hotel, held_band = self.viewCurrentSlots()
            hotel_slots = {slot['id'] for slot in held_hotel if slot is not None}
            band_slots = {slot['id'] for slot in held_band if slot is not None}

            # Track which slots failed to cancel
            failed_hotel_slots = []
            failed_band_slots = []

            # Cancel hotel slots with individual exception handling
            for slot in hotel_slots:
                try:
                    self.enforce_rate_limit()
                    self.hotel.release_slot(slot)
                    print(f"Cancelled hotel slot {slot}")
                except Exception as e:
                    print(f"Failed to cancel hotel slot {slot}: {e}")
                    failed_hotel_slots.append(slot)

            # Cancel band slots with individual exception handling
            for slot in band_slots:
                try:
                    self.enforce_rate_limit()
                    self.band.release_slot(slot)
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

    def reserveEarliestSlot(self):
        """
        Reserves the earliest matching pair of slots (hotel and band).
        Handles reservation limits by cleaning up unmatched slots first.
        """
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            try:
                # First, let's see what slots we already have
                self.enforce_rate_limit()
                held_hotel, held_band = self.viewCurrentSlots()

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
                        self.enforce_rate_limit()
                        self.hotel.release_slot(slot_id)

                    # Cancel unmatched band slots to free up reservation capacity
                    for slot_id in unmatched_band:
                        print(f"Cancelling unmatched band slot {slot_id} to free up capacity")
                        self.enforce_rate_limit()
                        self.band.release_slot(slot_id)

                    # Refresh our slot data after cancellations
                    self.enforce_rate_limit()
                    held_hotel, held_band = self.viewCurrentSlots()
                    hotel_slots_held = {int(slot['id']) for slot in held_hotel if slot is not None}
                    band_slots_held = {int(slot['id']) for slot in held_band if slot is not None}
                    matching_slots_held = hotel_slots_held & band_slots_held

                # Get available matching slots
                self.enforce_rate_limit()
                earliest_slots = self.viewFirst5FreeSlots().get("matching", [])

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
                        self.enforce_rate_limit()
                        self.cancelSlot(earliest_held)

                # Determine what needs to be reserved
                need_hotel = earliest_slot_to_reserve not in hotel_slots_held
                need_band = earliest_slot_to_reserve not in band_slots_held

                # Track what was newly reserved in this attempt
                newly_reserved_hotel = False
                newly_reserved_band = False

                # Reserve only what's needed
                if need_hotel and need_band:
                    print(f"Attempting to reserve both hotel and band for slot {earliest_slot_to_reserve}")
                    self.enforce_rate_limit()
                    hotel_response, band_response = self.reserveSlot(earliest_slot_to_reserve)
                    newly_reserved_hotel = bool(hotel_response)
                    newly_reserved_band = bool(band_response)
                elif need_hotel:
                    print(f"Band slot {earliest_slot_to_reserve} already held, reserving hotel only")
                    self.enforce_rate_limit()
                    hotel_response, _ = self.reserveSlot(earliest_slot_to_reserve, 'hotel')
                    newly_reserved_hotel = bool(hotel_response)
                    band_response = True  # Already held
                elif need_band:
                    print(f"Hotel slot {earliest_slot_to_reserve} already held, reserving band only")
                    self.enforce_rate_limit()
                    _, band_response = self.reserveSlot(earliest_slot_to_reserve, 'band')
                    newly_reserved_band = bool(band_response)
                    hotel_response = True  # Already held
                else:
                    print(f"Slot {earliest_slot_to_reserve} status is inconsistent")
                    hotel_response = band_response = False

                # Check if reservation was successful
                if hotel_response and band_response:
                    print(f"Successfully reserved matching pair for slot {earliest_slot_to_reserve}")

                    # Clean up any remaining unmatched slots
                    self.enforce_rate_limit()
                    self.cancelAllUnmatchedSlots()
                    return True
                else:
                    # Rollback any partial reservation we just made
                    if newly_reserved_hotel and not band_response:
                        print(f"Rolling back hotel reservation for slot {earliest_slot_to_reserve}")
                        self.enforce_rate_limit()
                        self.hotel.release_slot(earliest_slot_to_reserve)

                    if newly_reserved_band and not hotel_response:
                        print(f"Rolling back band reservation for slot {earliest_slot_to_reserve}")
                        self.enforce_rate_limit()
                        self.band.release_slot(earliest_slot_to_reserve)

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
