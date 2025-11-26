from mock_reservation_api import MockReservationApi
from booking_service import BookingService
import time

def run_demo():
    print("Starting Demo...")
    
    # Setup Mock APIs
    hotel_api = MockReservationApi("http://hotel", "key", 3, 0.1)
    band_api = MockReservationApi("http://band", "key", 3, 0.1)
    
    service = BookingService(hotel_api, band_api)
    
    print("\n1. View Available Slots")
    slots = service.viewFirst20FreeSlots()
    print(f"Hotel: {[s for s in slots['hotel'][:5]]}...")
    print(f"Band: {[s for s in slots['band'][:5]]}...")
    
    print("\n2. Reserve Earliest Matching Slot")
    success = service.reserveEarliestSlot()
    print(f"Reservation Success: {success}")
    
    print("\n3. View Held Slots")
    held_hotel, held_band = service.viewCurrentSlots()
    print(f"Held Hotel: {[s['id'] for s in held_hotel]}")
    print(f"Held Band: {[s['id'] for s in held_band]}")
    
    print("\n4. Cancel All Reservations")
    service.cancelAllSlots()
    
    print("\n5. Verify Cancellation")
    held_hotel, held_band = service.viewCurrentSlots()
    print(f"Held Hotel: {held_hotel}")
    print(f"Held Band: {held_band}")
    
    print("\nDemo Completed Successfully!")

if __name__ == "__main__":
    run_demo()
