# Copyright (c) 2025 Efstratios Goudelis
# Modifications and extensions Copyright (C) 2026 DynamiX-Labs
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


"""
Constants module for Ground Station application.
Contains all magic strings used throughout the application for consistency and maintainability.
"""


# ============================================================================
# Socket.IO Event Names (client-facing events)
# ============================================================================
class SocketEvents:
    """Socket.IO event names emitted to clients"""

    # Satellite Tracking
    SATELLITE_TRACKING = "satellite-tracking"
    SATELLITE_TRACKING_V2 = "satellite-tracking-v2"
    UI_TRACKER_STATE = "ui-tracker-state"
    UI_TRACKER_STATE_V2 = "ui-tracker-state-v2"
    TRACKER_COMMAND_STATUS = "tracker-command-status"
    TRACKER_INSTANCES = "tracker-instances"

    # SDR Events
    SDR_STATUS = "sdr-status"
    SDR_CONFIG = "sdr-config"
    SDR_CONFIG_ERROR = "sdr-config-error"
    SDR_ERROR = "sdr-error"
    SDR_FFT_DATA = "sdr-fft-data"

    # Audio
    AUDIO_DATA = "audio-data"

    # Decoders (SSTV, AFSK, Morse, GMSK, etc.)
    DECODER_DATA = "decoder-data"

    # VFO
    VFO_STATES = "vfo-states"

    # TLE Sync
    SAT_SYNC_EVENTS = "sat-sync-events"

    # Performance Monitoring
    PERFORMANCE_METRICS = "performance-metrics"

    # System Info (CPU/MEM/Disk/OS) live updates
    SYSTEM_INFO = "system-info"

    # Self-Interference Canceller
    SIC_STATUS = "sic-status"

    # Doppler Predictor
    DOPPLER_CURVE = "doppler-curve"

    # TX Pipeline
    TX_SCHEDULE = "tx-schedule"
    TX_STATUS = "tx-status"
    TX_POWER_STATUS = "tx-power-status"
    TX_BURST_STATUS = "tx-burst-status"

    # Transponder
    TRANSPONDER_STATUS = "transponder-status"

    # APRS
    APRS_IGATE_STATUS = "aprs-igate-status"
    APRS_TRACKS = "aprs-tracks"
    APRS_TELEMETRY = "aprs-telemetry"

    # Duplex Calibration
    DUPLEX_CALIBRATION = "duplex-calibration"


# ============================================================================
# Queue Message Types (inter-process communication)
# ============================================================================
class QueueMessageTypes:
    """Message types used in multiprocessing queues between workers and main process"""

    # Worker → Main
    ERROR = "error"
    TERMINATED = "terminated"
    STREAMING_START = "streamingstart"
    FFT_DATA = "fft_data"
    AUDIO_DATA = "audio-data"  # Note: uses hyphen to match Socket.IO event name
    CONFIG_ERROR = "config_error"

    # Main → Worker
    GET_CENTER_FREQ = "get_center_freq"


# ============================================================================
# Tracking State Names (database keys)
# ============================================================================
class TrackingStateNames:
    """Database tracking state names"""

    SATELLITE_TRACKING = "satellite-tracking"
    SATELLITE_TRACKING_PREFIX = "satellite-tracking:"


# ============================================================================
# Tracking State Values
# ============================================================================
class RotatorStates:
    """Allowed rotator state values in tracking_state."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TRACKING = "tracking"
    STOPPED = "stopped"
    PARKED = "parked"


class RigStates:
    """Allowed rig state values in tracking_state."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TRACKING = "tracking"
    STOPPED = "stopped"


class TrackerCommandStatus:
    """Tracker command lifecycle status values."""

    SUBMITTED = "submitted"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TrackerCommandScopes:
    """Tracker command target scopes."""

    ROTATOR = "rotator"
    RIG = "rig"
    TARGET = "target"
    TRACKING = "tracking"


# ============================================================================
# Tracking Event Names (nested event names in tracking messages)
# ============================================================================
class TrackingEvents:
    """Event names used in satellite tracking system"""

    # Satellite Events
    NORAD_ID_CHANGE = "norad_id_change"

    # Rotator Events
    ROTATOR_CONNECTED = "rotator_connected"
    ROTATOR_DISCONNECTED = "rotator_disconnected"
    ROTATOR_ERROR = "rotator_error"
    ROTATOR_PARKED = "rotator_parked"

    # Rotator Limit Events (specific)
    MIN_ELEVATION_OUT_OF_BOUNDS = "min_elevation_out_of_bounds"
    MAX_ELEVATION_OUT_OF_BOUNDS = "max_elevation_out_of_bounds"
    MIN_AZIMUTH_OUT_OF_BOUNDS = "min_azimuth_out_of_bounds"
    MAX_AZIMUTH_OUT_OF_BOUNDS = "max_azimuth_out_of_bounds"

    # Rotator Limit Events (deprecated - kept for backwards compatibility)
    AZIMUTH_OUT_OF_BOUNDS = "azimuth_out_of_bounds"
    ELEVATION_OUT_OF_BOUNDS = "elevation_out_of_bounds"

    # Rig Events
    RIG_CONNECTED = "rig_connected"
    RIG_DISCONNECTED = "rig_disconnected"
    RIG_ERROR = "rig_error"


# ============================================================================
# Command Types (tracker commands)
# ============================================================================
class TrackerCommands:
    """Commands that can be sent to the satellite tracker"""

    STOP = "stop"
    NUDGE_CLOCKWISE = "nudge_clockwise"
    NUDGE_COUNTER_CLOCKWISE = "nudge_counter_clockwise"
    NUDGE_UP = "nudge_up"
    NUDGE_DOWN = "nudge_down"


# ============================================================================
# Common Dictionary Keys
# ============================================================================
class DictKeys:
    """Common dictionary keys used throughout the application"""

    EVENT = "event"
    DATA = "data"
    EVENTS = "events"
    NAME = "name"
    TYPE = "type"
    CLIENT_ID = "client_id"
    MESSAGE = "message"
    SATELLITE_DATA = "satellite_data"
    TRACKING_STATE = "tracking_state"
    ROTATOR_DATA = "rotator_data"
    RIG_DATA = "rig_data"
