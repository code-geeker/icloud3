"""Support for tracking for iCloud devices."""

from .global_variables  import GlobalVariables as Gb
from .const             import (DOMAIN, ICLOUD3,
                                DISTANCE_TO_DEVICES,
                                NOT_SET, NOT_SET_FNAME, HOME, NOT_HOME,
                                DEVICE_TYPE_ICONS, DEVICE_TYPE_FNAME,
                                BLANK_SENSOR_FIELD, STATIONARY_FNAME,
                                TRACK_DEVICE, INACTIVE_DEVICE,
                                NAME, FNAME,
                                PICTURE,
                                LATITUDE, LONGITUDE,
                                DEVICE_TRACKER_STATE_VALUE, DEVICE_TRACKER_STATE_ZONE,
                                LOCATION_SOURCE, TRIGGER,
                                ZONE, ZONE_DATETIME,  LAST_ZONE, FROM_ZONE, ZONE_FNAME,
                                BATTERY,
                                CALC_DISTANCE, WAZE_DISTANCE, HOME_DISTANCE,
                                DEVICE_STATUS,
                                LAST_UPDATE, LAST_UPDATE_DATETIME,
                                NEXT_UPDATE, NEXT_UPDATE_DATETIME,
                                LAST_LOCATED, LAST_LOCATED_DATETIME,
                                GPS_ACCURACY,
                                CONF_DEVICE_TYPE, CONF_RAW_MODEL, CONF_MODEL, CONF_MODEL_DISPLAY_NAME,
                                CONF_TRACKING_MODE,
                                CONF_IC3_DEVICENAME,
                                )

EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
EVENT_DESCRIPTION = {EVENT_ENTER: "entering", EVENT_LEAVE: "leaving"}

from .helpers.common    import (instr, isnumber, is_statzone, zone_display_as)
from .helpers.messaging import (post_event,
                                log_info_msg, log_debug_msg, log_error_msg, log_exception,
                                _trace, _traceha, )
from .support           import start_ic3

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries       import ConfigEntry
from homeassistant.core                 import HomeAssistant
from homeassistant.helpers.entity       import DeviceInfo
from homeassistant.helpers              import entity_registry as er, device_registry as dr

import logging
# _LOGGER = logging.getLogger(__name__)
_LOGGER = logging.getLogger(f"icloud3")

#-------------------------------------------------------------------------------------------
async def async_setup_scanner(hass: HomeAssistant, config, see, discovery_info=None):
    """Old way of setting up the iCloud tracker."""
    Gb.ha_config_platform_stmt = True
    _LOGGER.warning("ICLOUD3 ALERT: The HA `configuration.yaml` file contains a `PLATFORM: ICLOUD3` statement. iCloud3 v3 is "
                    "now an integration and does not use the `configuration.yaml` or `config_ic3.yam` files. \n\n"
                    "1. Remove `PLATFORM: ICLOUD3` statements from `configuration.yaml`.\n"
                    "2. Restart Home Assistant\n"
                    "3. Add iCloud3 on the `Devices & Settings > Integrations` screen\n"
                    "4. Configure iCloud3 on the Integrations screen\n"
                    "5. Restart iCloud3")
    return True

#-------------------------------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up iCloud3 device tracker component."""
    # Save the hass `add_entities` call object for use in config_flow for adding devices
    Gb.async_add_entities_device_tracker = async_add_entities

    try:
        if Gb.conf_file_data == {}:
            Gb.hass = hass
            start_ic3.initialize_directory_filenames()
            start_ic3.load_storage_icloud3_configuration_file()

        NewDeviceTrackers = []
        for conf_device in Gb.conf_devices:
            devicename = conf_device[CONF_IC3_DEVICENAME]
            Gb.conf_devicenames.append(devicename)

            if (devicename in Gb.DeviceTrackers_by_devicename
                    or conf_device[CONF_TRACKING_MODE] == INACTIVE_DEVICE):
                continue

            DeviceTracker = iCloud3_DeviceTracker(devicename, conf_device)

            if DeviceTracker:
                Gb.DeviceTrackers_by_devicename[devicename] = DeviceTracker
                NewDeviceTrackers.append(DeviceTracker)

        # Set the total count of the device_trackers that will be created
        if Gb.device_trackers_cnt == 0:
            Gb.device_trackers_cnt = len(NewDeviceTrackers)
            log_info_msg(f'Device Tracker entities created: {Gb.device_trackers_cnt}')

        if NewDeviceTrackers is not []:
            async_add_entities(NewDeviceTrackers, True)
            _get_ha_device_ids_from_device_registry(hass)

    except Exception as err:
        _LOGGER.exception(err)
        log_exception(err)
        log_msg = f"►INTERNAL ERROR (Create device_tracker loop-{err})"
        log_error_msg(log_msg)

#-------------------------------------------------------------------------------------------
def _get_ha_device_ids_from_device_registry(hass):
    '''
    Cycle thru the ha device registry, extract the iCloud3 entries and associate the
    ha device_id with the ic3_devicename parameters

    Check deleted entries first in case it was readded
    '''
    try:
        dev_reg = dr.async_get(hass)
        Gb.ha_device_id_by_devicename = {}

        for device, device_entry in dev_reg.deleted_devices.items():
            _get_ha_device_id_from_device_entry(hass, device, device_entry)
        for device, device_entry in dev_reg.devices.items():
            _get_ha_device_id_from_device_entry(hass, device, device_entry)

    except Exception as err:
        log_exception(err)
        pass

#-------------------------------------------------------------------------------------------
def _get_ha_device_id_from_device_entry(hass, device, device_entry):
    '''
    For each entry in the device registry, determine if it is an iCloud3 entry (iCloud3 is in
    the device_entry.identifiers field. If so, check the other items, determine if one is a
    tracked devicename and, if so, extract the device_id for that tracked devicename. This is
    used to associate the sensors with the device in sensor.py.
    )

    DeviceEntry(area_id=None, config_entries={'4ff81e71befd8994712d56eadf7232ae'},
        configuration_url=None, connections=set(), disabled_by=None, entry_type=None,
        hw_version=None,
        id='306278916dc4a3b7bcc73b66dcd565b3',
        identifiers={('iCloud3', 'gary_iphone', 'iPhone 14 Pro')}, manufacturer='Apple',
        model='iPhone 14 Pro', name_by_user=None, name='Gary', suggested_area=None, sw_version=None,
        via_device_id=None, is_new=False)
    DeletedDeviceEntry(config_entries={'4ff81e71befd8994712d56eadf7232ae'},
        connections=set(), identifiers={('iCloud3', 'gary_ihone', 'iPhone 14 Pro')},
        id='9045bf3f0363c28957353cf2c47163d0', orphaned_timestamp=None
    '''
    try:
        de_identifiers = device_entry.identifiers
        for identifiers in de_identifiers:
            if 'iCloud3' in identifiers:
                for item in identifiers:
                    if item in Gb.conf_devicenames:
                        Gb.ha_device_id_by_devicename[item] = device_entry.id
                        break

    except:
        pass

#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
class iCloud3_DeviceTracker(TrackerEntity):
    """iCloud3 device_tracker entity definition."""

    def __init__(self, devicename, conf_device):
        """Set up the iCloud3 device_tracker entity."""

        try:
            self.hass          = Gb.hass
            self.devicename    = devicename
            self.Device        = None   # Filled in after Device object has been created in start_ic3
            self.entity_id     = f"device_tracker.{devicename}"
            self.device_fname  = conf_device[FNAME]
            self.device_type   = conf_device[CONF_DEVICE_TYPE]
            self.tracking_mode = conf_device[CONF_TRACKING_MODE]
            self.raw_model     = conf_device[CONF_RAW_MODEL]                # iPhone15,2
            self.model         = conf_device[CONF_MODEL]                    # iPhone
            self.model_display_name = conf_device[CONF_MODEL_DISPLAY_NAME]  # iPhone 14 Pro

            try:
                self.default_value = Gb.restore_state_devices[devicename]['sensors'][ZONE]
            except:
                self.default_value = BLANK_SENSOR_FIELD

            self.from_state_zonee   = ''
            self.to_state_zone      = ''
            self._state             = self.default_value
            self._attr_force_update = True
            self._unsub_dispatcher  = None
            self._on_remove         = [self.after_removal_cleanup]
            self.entity_removed_flag = False

            Gb.device_trackers_created_cnt += 1
            log_debug_msg(f'Device Tracker entity created: {self.entity_id}, #{Gb.device_trackers_created_cnt}')

        except Exception as err:
            log_exception(err)
            log_msg = f"►INTERNAL ERROR (Create device_tracker object-{err})"
            log_error_msg(log_msg)

#-------------------------------------------------------------------------------------------
    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_{self.devicename}"

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device_fname

    @property
    def location_name(self):
        """Return the location name of the device."""
        try:
            if self.state_value_not_set:
                return self.default_value

            return self._get_sensor_value(DEVICE_TRACKER_STATE_VALUE)
        except:
            return self.default_value

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device."""
        return self._get_sensor_value(GPS_ACCURACY, number=True)

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return str(self._get_sensor_value(LATITUDE, number=True))

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return str(self._get_sensor_value(LONGITUDE, number=True))

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._get_sensor_value(BATTERY, number=True)

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return "gps"

    @property
    def icon(self):
        """Return an icon based on the type of the device."""
        return DEVICE_TYPE_ICONS.get(self.device_type, "mdi:cellphone")

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._get_extra_attributes()

    @property
    def device_info(self):
        """Return the device information."""

        return DeviceInfo(  identifiers  = {(DOMAIN, self.devicename)},
                            manufacturer = "Apple",
                            model        = self.raw_model,
                            name         = f"{self.device_fname} ({self.devicename})",
                        )
#-------------------------------------------------------------------------------------------
    def _get_extra_attributes(self):
        '''
        Get the extra attributes for the device_tracker
        '''
        try:
            extra_attrs = {}

            extra_attrs['data_source']       = f"{self._get_sensor_value(LOCATION_SOURCE)} (iCloud3)"
            extra_attrs[DEVICE_STATUS]       = self._get_sensor_value(DEVICE_STATUS)
            extra_attrs[NAME]                = self._get_sensor_value(NAME)
            extra_attrs[PICTURE]             = self._get_sensor_value(PICTURE)
            extra_attrs[ZONE]                = self._get_sensor_value(ZONE)
            extra_attrs[LAST_ZONE]           = self._get_sensor_value(LAST_ZONE)
            extra_attrs[ZONE_DATETIME]       = self._get_sensor_value(ZONE_DATETIME)
            extra_attrs[LAST_LOCATED]        = self._get_sensor_value(LAST_LOCATED_DATETIME)
            extra_attrs[LAST_UPDATE]         = self._get_sensor_value(LAST_UPDATE_DATETIME)
            extra_attrs[HOME_DISTANCE]       = self._get_sensor_value(HOME_DISTANCE)
            extra_attrs[DISTANCE_TO_DEVICES] = self._get_sensor_value(DISTANCE_TO_DEVICES)

            if self.Device and self.Device.is_tracked:
                extra_attrs[NEXT_UPDATE]     = self._get_sensor_value(NEXT_UPDATE_DATETIME)
                extra_attrs[TRIGGER]         = self._get_sensor_value(TRIGGER)
                extra_attrs[FROM_ZONE]       = self._get_sensor_value(FROM_ZONE)
                extra_attrs[WAZE_DISTANCE]   = self._get_sensor_value(WAZE_DISTANCE)
                extra_attrs[CALC_DISTANCE]   = self._get_sensor_value(CALC_DISTANCE)

            if self.Device:
                if  self.Device.track_from_zones != [HOME]:
                    extra_attrs['track_from_zones'] = ', '.join(self.Device.track_from_zones)
                if  self.Device.track_from_base_zone != HOME:
                    extra_attrs['primary_home_zone'] = zone_display_as(self.Device.track_from_base_zone)

            extra_attrs['icloud3_version']     = Gb.version
            extra_attrs['event_log_version']   = Gb.version_evlog
            extra_attrs['tracking']            = ', '.join(Gb.Devices_by_devicename.keys())
            extra_attrs['icloud3_directory']   = Gb.icloud3_directory

            return extra_attrs

        except Exception as err:
            log_exception(err)
            log_error_msg(f"►INTERNAL ERROR (Create device_tracker object-{err})")

#-------------------------------------------------------------------------------------------
    def _get_sensor_value(self, sensor, number=False):
        '''
        Get the sensor value from Device's sensor
        '''
        try:
            not_set_value = 0 if number else BLANK_SENSOR_FIELD

            if self.Device is None:
                return self._get_restore_or_default_value(sensor, not_set_value)

            sensor_value = self.Device.sensors.get(sensor, None)

            if number and instr(sensor_value, ' '):
                sensor_value = sensor_value.split(' ')[0]

            number = isnumber(sensor_value)
            if number is False:
                if sensor_value is None or sensor_value.strip() == '' or sensor_value == NOT_SET:
                    sensor_value = BLANK_SENSOR_FIELD
                elif is_statzone(sensor_value):
                    sensor_value = STATIONARY_FNAME

        except Exception as err:
            log_exception(err)
            log_error_msg(f"►INTERNAL ERROR (Create device_tracker object-{err})")
            sensor_value = not_set_value

        return sensor_value

#-------------------------------------------------------------------------------------------
    def _get_restore_or_default_value(self, sensor, not_set_value):
        '''
        Get a default value that is used when iCloud3 has not started or the Device for the
        sensor has not veen created.
        '''
        try:
            sensor_value = Gb.restore_state_devices[self.devicename]['sensors'][sensor]
        except:
            sensor_value = not_set_value

        return sensor_value

#-------------------------------------------------------------------------------------------
    def _get_attribute_value(self, attribute):
        '''
        Get the attribute value from Device's attributes
        '''
        try:
            if self.Device is None:
                return 0

            attr_value = self.Device.attrs.get(attribute, None)

            if attr_value is None or attr_value.strip() == '' or attr_value == NOT_SET:
                attr_value = 0

        except:
            attr_value = 0

        return attr_value

#-------------------------------------------------------------------------------------------
    @property
    def state_value_not_set(self):
        state_value = self._get_sensor_value(DEVICE_TRACKER_STATE_VALUE)

        if self.Device is None:
            return True

        if (type(state_value) is str
                and (state_value.startswith(BLANK_SENSOR_FIELD)
                    or state_value.strip() == ''
                    or state_value == NOT_SET
                    or state_value == NOT_SET_FNAME)):
            return True
        else:
            return False

#-------------------------------------------------------------------------------------------
    def update_entity_attribute(self, new_fname=None):
        """ Update entity definition attributes """

        if (new_fname is None
                or self.Device.ha_device_id == ''):
            return

        self.device_fname = new_fname

        kwargs = {}
        kwargs['original_name'] = new_fname

        entity_registry = er.async_get(Gb.hass)
        er_entry = entity_registry.async_update_entity(self.entity_id, **kwargs)

        """
            Typically used:
                original_name: str | None | UndefinedType = UNDEFINED,

            Not used:
                area_id: str | None | UndefinedType = UNDEFINED,
                capabilities: Mapping[str, Any] | None | UndefinedType = UNDEFINED,
                config_entry_id: str | None | UndefinedType = UNDEFINED,
                device_class: str | None | UndefinedType = UNDEFINED,
                device_id: str | None | UndefinedType = UNDEFINED,
                disabled_by: RegistryEntryDisabler | None | UndefinedType = UNDEFINED,
                entity_category: EntityCategory | None | UndefinedType = UNDEFINED,
                hidden_by: RegistryEntryHider | None | UndefinedType = UNDEFINED,
                icon: str | None | UndefinedType = UNDEFINED,
                name: str | None | UndefinedType = UNDEFINED,
                new_entity_id: str | UndefinedType = UNDEFINED,
                new_unique_id: str | UndefinedType = UNDEFINED,
                original_device_class: str | None | UndefinedType = UNDEFINED,
                original_icon: str | None | UndefinedType = UNDEFINED,
                supported_features: int | UndefinedType = UNDEFINED,
                unit_of_measurement: str | None | UndefinedType = UNDEFINED,
    """

        kwargs = {}
        kwargs['name'] = f"{new_fname} ({self.devicename})"
        kwargs['name_by_user'] = ""

        device_registry = dr.async_get(Gb.hass)
        dr_entry = device_registry.async_update_device(self.Device.ha_device_id, **kwargs)

#-------------------------------------------------------------------------------------------
    def remove_device_tracker(self):
        try:
            Gb.hass.async_create_task(self.async_remove(force_remove=True))

        except Exception as err:
            _LOGGER.exception(err)

#-------------------------------------------------------------------------------------------
    def after_removal_cleanup(self):
        """ Cleanup device_tracker after removal

        Passed in the `self._on_remove` parameter during initialization
        and called by HA after processing the async_remove request
        """

        log_info_msg(f"Registered device_tracker.icloud3 entity removed: {self.entity_id}")

        self._remove_from_registries()
        self.entity_removed_flag = True

        if self.Device is None:
            return

        if self.Device.Sensors_from_zone and self.devicename in self.Device.Sensors_from_zone:
            self.Device.Sensors_from_zone.pop(self.devicename)

        if self.Device.Sensors and self.devicename in self.Device.Sensors:
            self.Device.Sensors.pop(self.devicename)

#-------------------------------------------------------------------------------------------
    def _remove_from_registries(self) -> None:
        """ Remove entity/device from registry """

        if not self.registry_entry:
            return

        # Remove from device registry.
        if device_id := self.registry_entry.device_id:
            device_registry = dr.async_get(self.hass)
            if device_id in device_registry.devices:
                device_registry.async_remove_device(device_id)

        # Remove from entity registry.
        if entity_id := self.registry_entry.entity_id:
            entity_registry = er.async_get(Gb.hass)
            if entity_id in entity_registry.entities:
                entity_registry.async_remove(entity_id)

#-------------------------------------------------------------------------------------------
    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

#-------------------------------------------------------------------------------------------
    def write_ha_device_tracker_state(self):
        """Update the entity's state."""

        try:
            self.async_write_ha_state()

            # Save the updated zone (location_name) to see if a zone trigger enter/leave needs
            # to be issued in device.write_ha_device_tracker_state, the function that calls
            # this function
            self.from_state_zone = self.to_state_zone
            self.to_state_zone   = self._get_sensor_value(DEVICE_TRACKER_STATE_ZONE)

            self._check_zone_change_trigger()
            return

        except Exception as err:
            log_exception(err)

#--------------------------------------------------------------------
    def _check_zone_change_trigger(self):

        # A one change triggers a zone enter/leave event. Determine the type of trigger and
        # issue the appropriate one

        # zone --> not_home = leave zone
        # zone --> zone     = leave, enter
        # not_home --> zone = enter zone

        return

        # if self.from_state_zone == self.to_state_zone:
        #     return

        # # Leaving a zone
        # if self.from_state_zone != NOT_HOME:
        #     self._issue_zone_change_trigger('leave')

        # # entering a zone
        # if self.to_state_value != NOT_HOME:
        #     self._issue_zone_change_trigger('enter')

#--------------------------------------------------------------------
    # def _issue_zone_change_trigger(self, event):
    #     msg = (f"ZoneTrigger > {event}, {self.from_state_zone} --> {self.to_state_zone} ")
    #     _trace(self.devicename, msg)
    #     pass

    #     description = (f"{self.entity_id}, {EVENT_DESCRIPTION[event]}, "
    #                     f"{self._get_sensor_value(ZONE_FNAME)}")
    #     trigger_data = trigger_info["trigger_data"]

    #     Gb.hass.async_run_hass_job(
    #             job,
    #             {
    #                 "trigger": {
    #                     **trigger_data,
    #                     "platform": "zone",
    #                     "entity_id": self.entity_id,
    #                     "from_state": self.from_state_zone,
    #                     "to_state": self.to_state_zone,
    #                     "zone": self._get_sensor_value(ZONE),
    #                     "event": event,
    #                     "description": description,
    #                 }
    #             },
    #             to_s.context if to_s else None,
    #         )

#-------------------------------------------------------------------------------------------
    def __repr__(self):
        return (f"<DeviceTracker: {self.devicename}/{self.device_type}>")
