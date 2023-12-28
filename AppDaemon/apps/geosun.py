import hassapi as hass
import mqttapi as mqtt
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

class Geosun(hass.Hass):
    def initialize(self):
        # configuration parameters from app.yaml
        self.url = 'http://' + self.args["source"]
        self.user = self.args["user"]
        self.password = self.args["password"]
        self.payload = {'USER':self.user, 'PASS':self.password}
        self.device_id = self.args["device_id"]
        self.device_name = self.args["device_name"]
        self.device_model = self.args["device_model"]
        self.device_manufacturer = self.args["device_manufacturer"]
        self.home_assistant_base_topic = self.args["home_assistant_base_topic"]
        
        #configuration parameters internal
        self.topic_paths = {"config":"config","state":"state","command":"set"}
        self.entity_types= {"se":"sensor","sw":"switch","bs":"binary_sensor","nu":"number", "tx":"text"}

        # update interval, first run delay 
        interval = int(self.args["interval"])
        startAt = datetime.now() + timedelta(seconds = 5)

        if interval < 15:
            raise Exception("Update interval {} must be at least 15 seconds".format(interval))

        # delay first launch with 'interval' , run every 'interval' seconds
        self.run_every(self.updateState, startAt, interval)
        
        # initialize MQTT and connect to broker
        self.mqtt = self.get_plugin_api("MQTT")
        self.log('MQTT connected' if self.mqtt.is_client_connected() else 'MQTT not connected' )

        # subscribe command topics
        self.mqtt.mqtt_subscribe("{}/switch/{}/+/{}".format(self.home_assistant_base_topic, self.device_name, self.topic_paths["command"]))
        self.mqtt.mqtt_subscribe("{}/number/{}/+/{}".format(self.home_assistant_base_topic, self.device_name, self.topic_paths["command"]))
        self.mqtt.mqtt_subscribe("{}/text/{}/+/{}".format(self.home_assistant_base_topic, self.device_name, self.topic_paths["command"]))
        self.mqtt.listen_event(self.events_callback,"MQTT_MESSAGE")

        #create device and entities in HA 
        self.initializeEntities()

    def updateState(self, kwargs):
        self.updateEntities(list(self.entities.keys()))

    def initializeEntities(self):
        self.defineDevice()
        self.defineEntities()
        
        for entity in self.entities:
            entity_type = self.entity_types[self.entities[entity][2]]
            payload = '{'
            payload += '"object_id":"{}"'.format(entity)
            payload += ',"unique_id":"{}"'.format(entity)
            payload += ',"name":"{}"'.format(self.entities[entity][3])
            payload += ',"device_class":"{}"'.format(self.entities[entity][4]) if self.entities[entity][4] != "" else ""
            payload += ',"icon":"{}"'.format(self.entities[entity][5])
            if self.entities[entity][2] == "se":
                payload += ',"unit_of_measurement":"{}"'.format(self.entities[entity][6]) if self.entities[entity][6] != "" else ""
                payload += ',"suggested_display_precision":"{}"'.format(self.entities[entity][7])
            if self.entities[entity][2] == "sw":
                payload += ',"payload_on":"{}"'.format(self.entities[entity][6])
                payload += ',"payload_off":"{}"'.format(self.entities[entity][7])
                payload += ',"command_topic":"{}"'.format(self.getTopic(entity_type,'command', entity))
            if self.entities[entity][2] == "bs":
                payload += ',"payload_on":"{}"'.format(self.entities[entity][6])
                payload += ',"payload_off":"{}"'.format(self.entities[entity][7])
            if self.entities[entity][2] == "nu":
                payload += ',"unit_of_measurement":"{}"'.format(self.entities[entity][6]) if self.entities[entity][6] != "" else ""
                payload += ',"suggested_display_precision":"{}"'.format(self.entities[entity][7])
                payload += ',"mode":"{}"'.format(self.entities[entity][8])
                payload += ',"min":"{}"'.format(self.entities[entity][9])
                payload += ',"max":"{}"'.format(self.entities[entity][10])
                payload += ',"step":"{}"'.format(self.entities[entity][11])
                payload += ',"command_topic":"{}"'.format(self.getTopic(entity_type,'command', entity))
            if  self.entities[entity][2] == "tx":
                payload += ',"pattern":"{}"'.format(self.entities[entity][6])
                payload += ',"command_topic":"{}"'.format(self.getTopic(entity_type,'command', entity))          
            payload += ',"state_topic":"{}"'.format(self.getTopic(entity_type, 'state', entity))
            payload += ',{}'.format(self.device)
            payload += '}'
            config_topic = self.getTopic(entity_type, 'config', entity) 
            #self.log("Entity config topic: {}, Payload: {}".format(config_topic, payload))
            self.mqtt.mqtt_publish(topic = config_topic, payload = payload)
        
    def defineDevice(self):
        self.device = '"device":{{"identifiers":["{}"], "model":"{}", "name":"{}","manufacturer":"{}"}}'.format(self.device_id, self.device_model, self.device_name, self.device_manufacturer)

    def events_callback(self, event_name, data, cb_args):
        topic = data["topic"]
        wildcard = data['wildcard']
        payload = data["payload"]
        # self.log("Callback: {}".format(data))

        entity = topic.partition(wildcard.partition('+')[0])[2].partition(wildcard.partition('+')[2])[0]
        entity_to_update =[]
        entity_to_update.append(entity)
        
        self.updateDeviceValue(entity, payload)
        self.updateEntities(entity_to_update)

    def updateEntities(self, entities_to_update):
        with requests.Session() as s:
            if self.logInToDevice(s):
                
                xml_pages = set()
                for entity in entities_to_update:
                    xml_pages.add(self.entities[entity][0])
                
                device_values={}
                for page in xml_pages:
                    res = s.get("{}/{}".format(self.url, page))
                    xml = ET.fromstring(res.text)
                    for input in xml.iter('INPUT'):
                        device_values[input.attrib.get('NAME')] = input.attrib.get('VALUE')

                for entity in entities_to_update:
                    if self.entities[entity][1] in device_values:
                        topic = self.getTopic(self.entity_types[self.entities[entity][2]],"state",entity)
                        payload = device_values[self.entities[entity][1]]
                        # self.log("Entity update topic: {}, payload: {}".format(topic, payload))
                        self.mqtt.mqtt_publish(topic = topic, payload = payload)
                
                self.logOutOfDevice(s)
            s.close()

    def getTopic(self, obj_class, topic_type, obj):
        return "{}/{}/{}/{}/{}".format(self.home_assistant_base_topic, obj_class, self.device_name, obj, self.topic_paths[topic_type])

    def logInToDevice(self, session):
        res = session.post(self.url, data = self.payload)
        if res.url.capitalize().endswith('page159.xml'):
            return True
        else:
            self.log("Unable to log in to device")
            return False

    def logOutOfDevice(self, session):
        res = session.get("{}/LOGOUT.XML".format(self.url))
        return True if res.text.find("<LOGOUT>") !=-1 else False

    def updateDeviceValue(self, entity, value):
        update_url = "{}/{}".format(self.url, self.entities[entity][0])
        update_data = {}
        update_data[self.entities[entity][1]] = value
        # self.log("URL: {}, DATA: {}".format(update_url, update_data))
        
        with requests.Session() as s:
            if self.logInToDevice(s):
                res = s.post(update_url, data = update_data)
                # self.log("Result: {}, Text: {}".format(res.status_code, res.text))
            self.logOutOfDevice(s)
        s.close()

    def defineEntities(self):
        self.entities = {
            # sensor: object_id:[TECO XML page, TECO value, entity_type, name, device_class, icon, unit_of_measurement, suggested_display_precision]
            # switch: object_id:[TECO XML page, TECO value, entity_type, name, device_class, icon, payload_on, payload_off ]
            # binary_sensor: object_id:[TECO XML page, TECO value, entity_type, name, device_class, icon, payload_on, payload_off]
            # number: object_id:[TECO XML page, TECO value, entity_type, name, device_class, icon, unit_of_measurement, suggested_display_precision, mode, min, max, step]
            # text: object_id:[TECO XML page, TECO value, entity_type, name, device_class (emtpy - no device class), icon, pattern]
            
            # entity_type: se-sensor, sw-switch, bs-binary_sensor, nu-number, tx-text
            
            # -- SENSORS --
            "dhw_temperature":["PAGE144.XML","__T31CD7724_REAL_.1f","se","DHW temperature","temperature","mdi:water-boiler","°C",1]
            ,"hw_temperature":["PAGE133.XML","__TF420903F_REAL_.1f","se","HW temperature","temperature","mdi:water-boiler","°C",1]
            ,"hw_target_temperature":["PAGE133.XML","__TB12A6D9A_REAL_.1f","se","HW target temperature","temperature","mdi:water-boiler","°C",1]
            ,"heat_pump_power":["PAGE196.XML","__TA2C9CFCD_REAL_.2f","se","Heat pump power","power","mdi:heat-pump","kW", 2]
            ,"heat_pump_consumption":["PAGE196.XML","__T7816B7E5_REAL_.2f","se","Heat pump consumption","power","mdi:heat-pump","kW", 2]
            ,"heat_pump_COP":["PAGE196.XML", "__T1E26BB4F_REAL_.2f","se","Heat pump COP", "power_factor","mdi:heat-pump","", 2]
            ,"heat_pump_relative_power":["PAGE196.XML", "__TF7A12A3D_REAL_.0f","se","Heat pump relative power","power_factor","mdi:heat-pump","%",0]
            ,"water_heater_in":["PAGE196.XML", "__T7FEC1C3B_REAL_.1f","se","Water heater in", "temperature", "mdi:watermark","°C", 1]
            ,"water_heater_out":["PAGE196.XML", "__T20F39926_REAL_.1f","se","Water heater out","temperature","mdi:watermark","°C", 1]
            
            # -- SWITCHES --
            ,"hw_heater_setting":["PAGE132.XML", "__TDE1D9B85_BOOL_i","sw","HW heater","switch","mdi:toggle-switch",1,0]
            ,"dhw_heater_setting":["PAGE143.XML", "__TE5A77326_BOOL_i","sw","DHW heater","switch","mdi:toggle-switch",1,0]
            
            # -- BINARY SENSORS --
            ,"hw_heater_status":["PAGE132.XML","__T3E022662_BOOL_i","bs","HW heater","","mdi:fire",1, 0]
            ,"dhw_heater_status":["PAGE143.XML","__T8D88EB9A_BOOL_i","bs","DHW heater","","mdi:fire",1, 0]
            
            # -- NUMBERS --
            ,"DHW_temperature_setting":["PAGE144.XML","__TDF2423B2_REAL_.1f","nu","DHW temperature","temperature","mdi:water-boiler","°C",1, "slider",30,60,1]
            
            # -- TEXTS
            ,"DHW_heating_from":["PAGE144.XML","__T324BA0AB_TIME_Thh:mm","tx","DHW heating from","","mdi:clock-digital","([01]?[0-9]|2[0-3]):[0-5][0-9]"]
            ,"DHW_heating_to":["PAGE144.XML","__TB07A911F_TIME_Thh:mm","tx","DHW heating to","","mdi:clock-digital","([01]?[0-9]|2[0-3]):[0-5][0-9]"]
        }
