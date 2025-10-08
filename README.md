COMP28112: Atomic Resource Broker Client - Wedding Planner

Project Overview
This project implements a robust, multi-threaded client application in Python for managing critical resource reservations across two independent external REST APIs (simulating Hotel and Band services). The core technical focus is on client reliability, ensuring data consistency using atomic rollback logic, and maintaining a responsive User Interface (UI) despite external rate limits.

The solution utilizes an object-oriented API wrapper and a custom Tkinter GUI to demonstrate non-blocking, asynchronous handling of remote transactions.

Core Technical Features
Feature

Implementation

Key Benefits

Atomic Rollback Logic

Implemented within reserveSlot function (in booking.py). If a reservation succeeds on one API (e.g., Hotel) but fails on the other (e.g., Band), the first successful transaction is immediately canceled (released) to guarantee the system remains in a consistent state (ACID principle).

Guarantees cross-service data integrity; prevents partial, orphaned reservations.

Rate Limiting

Custom enforce_rate_limit() function (in booking.py) uses time.sleep() to ensure API calls are spaced out, preventing the client from overloading external servers.

Ensures compliance with external API usage policies and avoids 5xx server errors.

Asynchronous Processing

The Tkinter GUI uses the threading module to run all API calls (showCurrentSlots, reserveEarliestSlot, etc.) in background threads.

Maintains UI responsiveness and prevents the application from freezing ("blocking") while waiting for slow network responses.

Robust API Wrapper

ReservationApi class (in reservationapi.py) handles all external communication.

Automatically retries requests on server errors (5xx) and converts specific HTTP status codes (400, 401, 409) into descriptive Python exceptions (e.g., SlotUnavailableError).

Client-Side Caching

Implemented in ReservationApi to store the results of recent API calls (e.g., get_slots_held).

Reduces unnecessary network traffic and speeds up subsequent requests for static data, improving application performance.

Project Structure
.
├── api.ini              <-- Configuration file for API URLs, keys, and global settings (retries, delay).
├── booking.py           <-- Main application logic, multi-threading, atomic rollback, and Tkinter GUI.
├── reservationapi.py    <-- The REST API wrapper class with retry and caching logic.
└── exceptions.py        <-- Custom exception classes for specific API errors (400, 401, 409, 451).

Getting Started
Prerequisites
Python 3.8+

The requests and simplejson libraries.

pip install requests simplejson

Configuration
Ensure you have an api.ini file in the project root with the necessary URL and key structure (simulating the external Hotel and Band services):

[global]
retries = 3
delay = 0.2

[hotel]
url = <YOUR_HOTEL_API_BASE_URL>
key = <YOUR_HOTEL_API_KEY>

[band]
url = <YOUR_BAND_API_BASE_URL>
key = <YOUR_BAND_API_KEY>

Running the Application
Execute the main application file from your terminal:

python3 booking.py

Key Logic: Atomic Rollback
The reserveSlot function is designed to enforce atomicity for reservations requiring both services.

Attempt Reservation: Tries to reserve Hotel first, then Band.

Failure Check: If the Band reservation fails after the Hotel succeeded, the except block is triggered.

Rollback: The logic immediately calls hotel.release_slot(num) to cancel the successful Hotel reservation, returning the system to a clean, consistent state. This prevents the user from holding a partial reservation.

Author: a38062an (Anthony Nguyen)
Course: COMP28112 Advanced Computing Lab
Last Updated: October 2025
