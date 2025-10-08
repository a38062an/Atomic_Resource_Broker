This is a great project overview. I've reformatted it to be more professional and direct, removing course/author specifics and academic file references, and streamlining the language for a portfolio or technical documentation.

-----

#  Atomic Resource Broker Client: Technical Overview

This project implements a resilient, multi-threaded client application for managing shared, critical resources across independent external services via REST APIs. The design prioritizes **transactional integrity**, **client reliability**, and a responsive User Experience (UX).

##  Platform Scope & Objectives

The application acts as a **reliable service broker** that coordinates the allocation of time slots from two external APIs (Hotel and Band).

| **Objective** | **Outcome** |
| :--- | :--- |
| **Data Integrity** | Guarantee resource allocation is **atomic** (all or nothing) despite multi-service dependency. |
| **Concurrency** | Maintain a responsive GUI during slow, $1\text{s}$ minimum network operations. |
| **Resilience** | Automatically handle API errors and connection failures without crashing the application. |

##  Core Technical Features & Implementation

| Feature | Implementation | Key Benefits |
| :--- | :--- | :--- |
| **Atomic Rollback Logic** | Implemented within the core reservation function (`booking.py`). | **Guarantees transactional consistency (ACID Principle).** If one service reservation succeeds and the partner fails, the successful reservation is immediately canceled/released. |
| **Asynchronous Processing** | UI runs on the main thread; all network requests are delegated to the Python **`threading`** module. | Ensures the application remains **non-blocking** and highly responsive during network latency. |
| **Robust API Wrapper** | Custom `ReservationApi` class with explicit logic for error handling. | Maps generic $4\text{xx}/5\text{xx}$ HTTP status codes to **descriptive Python exceptions** (`SlotUnavailableError`), allowing for predictable failure handling and recovery. |
| **Rate Limiting** | Custom `enforce_rate_limit()` logic uses `time.sleep()` to calculate and enforce the $1\text{s}$ minimum delay between API calls. | Ensures compliance with external API policies and prevents unnecessary $429$ (Too Many Requests) errors. |
| **Client-Side Caching** | Implemented within the API wrapper to store frequently accessed data (e.g., held slots) for $60\text{s}$. | Reduces network traffic and minimizes response time for repeated status checks. |

##  Project Structure & Setup

### Architecture

The project maintains a clear separation between the UI, the business logic, and the communication layer:

  * **`booking.py`**: Main application entry point, contains the transactional logic (rollback), multi-threading setup, and the Tkinter GUI.
  * **`reservationapi.py`**: The API wrapper implementing retries, delay, and caching.
  * **`exceptions.py`**: Custom exception definitions for predictable error handling.
  * **`api.ini`**: Configuration file for service URLs, keys, and global parameters.

### Getting Started

**Prerequisites:** Python 3.8+, `requests`, and `simplejson` libraries.

**Configuration:** Ensure `api.ini` is configured with base URLs and keys for the simulated services:

```ini
[global]
retries = 3
delay = 0.2

[hotel]
url = <HOTEL_API_BASE_URL>
key = <HOTEL_API_KEY>
# ...and similar for [band]
```

**Run:** Execute the main application file from your terminal:
`python3 booking.py`
