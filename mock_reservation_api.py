import time
import random
from exceptions import (
    BadRequestError, InvalidTokenError, BadSlotError, NotProcessedError,
    SlotUnavailableError, ReservationLimitError)

class MockReservationApi:
    """
    This is a fake API that looks like the real one but just keeps track of things in memory.
    Useful for testing when you don't have a real server running.
    """
    def __init__(self, base_url: str, token: str, retries: int, delay: float):
        self.base_url = base_url
        self.token = token
        self.retries = retries
        self.delay = delay
        
        # Fake database of slots
        # We'll create 100 slots, some random ones already taken
        self.slots = {}
        for i in range(1, 101):
            self.slots[i] = {'id': i, 'available': True, 'held_by_us': False}
            
        # Randomly make some unavailable to look realistic
        for i in range(1, 101):
            if random.random() < 0.3: # 30% chance slot is taken by someone else
                self.slots[i]['available'] = False

    def get_slots_available(self):
        """Return list of available slots, just like the real API"""
        time.sleep(self.delay) # Fake network delay
        
        available = []
        for i in self.slots:
            if self.slots[i]['available'] and not self.slots[i]['held_by_us']:
                available.append({'id': i})
                
        return available

    def get_slots_held(self):
        """Return list of slots we are holding"""
        time.sleep(self.delay)
        
        held = []
        for i in self.slots:
            if self.slots[i]['held_by_us']:
                held.append({'id': i})
                
        return held

    def release_slot(self, slot_id):
        """Release a slot we are holding"""
        time.sleep(self.delay)
        
        slot_id = int(slot_id)
        if slot_id not in self.slots:
            raise BadSlotError("Slot does not exist")
            
        if not self.slots[slot_id]['held_by_us']:
            # In the real API this might be 404 or 409, but let's say it's fine or ignored
            return {'message': 'Slot released'}
            
        self.slots[slot_id]['held_by_us'] = False
        self.slots[slot_id]['available'] = True
        return {'message': 'Slot released'}

    def reserve_slot(self, slot_id):
        """Try to reserve a slot"""
        time.sleep(self.delay)
        
        slot_id = int(slot_id)
        if slot_id not in self.slots:
            raise BadSlotError("Slot does not exist")
            
        # Check if we already hold too many (limit is usually 2)
        held_count = sum(1 for s in self.slots.values() if s['held_by_us'])
        if held_count >= 2:
            raise ReservationLimitError("You already have 2 slots")
            
        if not self.slots[slot_id]['available']:
            raise SlotUnavailableError("Slot is already taken")
            
        self.slots[slot_id]['held_by_us'] = True
        self.slots[slot_id]['available'] = False
        return {'message': 'Slot reserved'}
