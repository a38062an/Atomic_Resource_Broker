""" Reservation API wrapper

This class implements a simple wrapper around the reservation API. It
provides automatic retries for server-side errors, delays to prevent
server overloading, and produces sensible exceptions for the different
types of client-side error that can be encountered.
"""
from cgitb import reset
from urllib.parse import urljoin

# This file contains areas that need to be filled in with your own
# implementation code. They are marked with "Your code goes here".
# Comments are included to provide hints about what you should do.

import requests
import simplejson
import warnings
import time

from requests.exceptions import HTTPError
from exceptions import (
    BadRequestError, InvalidTokenError, BadSlotError, NotProcessedError,
    SlotUnavailableError,ReservationLimitError)

class ReservationApi:
    def __init__(self, base_url: str, token: str, retries: int, delay: float):
        """ Create a new ReservationApi to communicate with a reservation
        server.

        Args:
            base_url: The URL of the reservation API to communicate with.
            token: The user's API token obtained from the control panel.
            retries: The maximum number of attempts to make for each request.
            delay: A delay to apply to each request to prevent server overload.
        """
        self.base_url = base_url
        self.token    = token
        self.retries  = retries
        self.delay    = delay

    def _reason(self, req: requests.Response) -> str:
        """Obtain the reason associated with a response"""
        reason = ''

        # Try to get the JSON content, if possible, as that may contain a
        # more useful message than the status line reason
        try:
            json = req.json()
            reason = json['message']

        # A problem occurred while parsing the body - possibly no message
        # in the body (which can happen if the API really does 500,
        # rather than generating a "fake" 500), so fall back on the HTTP
        # status line reason
        except simplejson.errors.JSONDecodeError:
            if isinstance(req.reason, bytes):
                try:
                    reason = req.reason.decode('utf-8')
                except UnicodeDecodeError:
                    reason = req.reason.decode('iso-8859-1')
            else:
                reason = req.reason

        return reason


    def _headers(self) -> dict:
        """Create the authorization token header needed for API requests"""
        # Your code goes here
        header = {"Authorization": "Bearer " + self.token} # Create dictionary with "Authorization" key and value
        return header

    def _send_request(self, method: str, endpoint: str) -> dict:
        """Send a request to the reservation API and convert errors to
           appropriate exceptions"""

        url = urljoin(self.base_url, endpoint)  # Use urljoin to properly combine URLs
        # Attempt to perform the request, retrying if necessary
        print(url)

        for attempt in range(self.retries):
            try:
                headers = self._headers()
                response = requests.request(method, url, headers=headers)

                # This will raise an HTTPError if the response was an HTTP error
                response.raise_for_status()

                time.sleep(self.delay)  # Delay before processing the response

                return response.json()  # Return the JSON data (200 response)

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                reason = self._reason(e.response)

                if 500 <= status_code < 600:
                    warnings.warn(f"Server error: {reason} (attempt {attempt + 1})")
                    if attempt < self.retries - 1:
                        time.sleep(self.delay)
                    continue
                elif 400 <= status_code < 500:
                    if status_code == 400:
                        raise BadRequestError(reason)
                    elif status_code == 401:
                        raise InvalidTokenError(reason)
                    elif status_code == 403:
                        raise BadSlotError(reason)
                    elif status_code == 404:
                        raise NotProcessedError(reason)
                    elif status_code == 409:
                        raise SlotUnavailableError(reason)
                    elif status_code == 451:
                        raise ReservationLimitError(reason)
                    else:
                        raise HTTPError(f"Unexpected client error: {reason}")
                else:
                    raise HTTPError(f"Unexpected status code {status_code}: {reason}")

            except requests.exceptions.ConnectionError as e:
                print(f"Connection error (try {attempt + 1}/{self.retries}): {e}")
                if attempt < self.retries - 1:
                    time.sleep(self.delay)

            except requests.exceptions.Timeout as e:
                print(f"Timeout error (try {attempt + 1}/{self.retries}): {e}")
                if attempt < self.retries - 1:
                    time.sleep(self.delay)

            except simplejson.errors.JSONDecodeError as e:
                print(f"JSON decode error (try {attempt + 1}/{self.retries}): {e}")
                if attempt < self.retries - 1:
                    time.sleep(self.delay)

            except requests.exceptions.RequestException as e:
                raise HTTPError(f"Request error: {e}")

        # If we've exhausted all retries
        raise HTTPError(f"Failed after {self.retries} attempts")

        # Allow for multiple retries if needed
            # To Perform the request.

            # Delay before processing the response to avoid swamping server.

            # 200 response indicates all is well - send back the json data.

            # 5xx responses indicate a server-side error, show a warning
            # (including the try number).

            # 400 errors are client problems that are meaningful, so convert
            # them to separate exceptions that can be caught and handled by
            # the caller.

            # Anything else is unexpected and may need to kill the client.

        # Get here and retries have been exhausted, throw an appropriate
        # exception.


    def get_slots_available(self):
        """Obtain the list of slots currently available in the system"""
        # Your code goes here
        response = self._send_request('GET', 'reservation/available')
        return response

    def get_slots_held(self):
        """Obtain the list of slots currently held by the client"""
        # Your code goes here
        response = self._send_request('GET', f"reservation")
        return response

    def release_slot(self, slot_id):
        """Release a slot currently held by the client"""
        # Your code goes here
        response = self._send_request('DELETE', f"reservation/{slot_id}")

    def reserve_slot(self, slot_id):
        """Attempt to reserve a slot for the client"""
        # Your code goes here
        response = self._send_request('POST', f"reservation/{slot_id}")
        return response