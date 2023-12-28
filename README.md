# Integrace tepelného čerpadla MITSUBISHI a jednotky GEOSUN Eco One do Home Assistant
## MQTT
Integrace využívá MQTT pro vytváření a aktualizaci zařízení a entit. Proto potřebuje MQTT broker. 
Doporučuji použít doplněk Mosquitto broker - standardně v obchodě s doplňky Home Assistant.
Konfigurace doplňku může být výchozí. Pro přihlášení k brokeru je vhodné vytvořit samostatný uživateslký účet v Home Assistant - Nastavení - Osoby - Uživatelé
## AppDaemon
Integrace je vytvořena jako aplikace v doplňku AppDaemon - standardně v obchodě s doplňky Home Assistant.
AppDeamon musí být nakonfigurován pro komunikaci s MQTT brokerem (Mosquitto) v souboru appdaemon.yaml [vzor](AppDaemon/appdaemon.yaml)
Konfigurační parametry integrační aplikace se nastavují v souboru apps.yaml [vzor](AppDaemon/apps/apps.yaml)
Vlastní aplikaci včetně definice entit tvoří soubor geosun.py [vzor](AppDaemon/apps/geosun.py)
Aplikace po spuštění vytvoří v MQTT integraci nové zařízení s definovynými entitami a zajišťuje komunikaci s jednotkou Eco One a obousměrnou aktualizaci stavu entit. 
### Entity
Do integrace lze snadno přidat další entity doplněním proměnné **self.entities** v souboru [geosun.py](AppDaemon/apps/geosun.py
Aktuálně jsou podporovány entity typu sensor, binary sensor, switch, number, text.
Názvy proměnných (obvykle začínají __) lze ve webovém prostředí jednotky Eco One vyčíst ze zdrojového kód přislušné XML stránky (Ctrl + U v prohlížečích Chrome, Edge)     

_Tipy:_
- AppDaemon restaruje aplikaci při každé změně souborů yaml a py. Pozor při úpravách entit !!
- Pro editaci souborů lze vhodně využit doplněk Studio Code Server, standardně obsaženýv obchodě s doplňky Home Assistant. Ukládá soubor automaticky při každé změně obsahu (viz. předchozí bod)!

