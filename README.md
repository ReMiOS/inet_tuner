# iNET Tuner
Denon / Marantz Receiver - Internet Radiostream Favorite editor making use op REST-API commands.<br>
Simple tool to edit internet radio stream favorites on Denon and Marantz receivers and streamers.<br>

Database scheme based on [YTuner](https://github.com/coffeegreg/YTuner) <br>
and updates from [Radio-Browser](https://api.radio-browser.info/)<br>

Tested on Denon DNP-F109

! Use at own risk !

# Screenshot
![iNET_Tuner](img/inet_tuner.png)  

# Denon REST-API commands

There is no known documentation about this REST-API from Denon.<br>
Depending on your model they can work (tested on Denon DNP F109)<br>
For instance the formiPhoneAppDirect.xml endpoint seems unavailable on Denon AVR X1300W<br>
Note that the AppCommand.xml endpoint expects an xml with linebreaks! (newline or carriage return)<br>
<br>
```
http://<receiver-ip>/goform/Deviceinfo.xml
http://<receiver-ip>/goform/formNetAudio_StatusXml.xml

http://<receiver-ip>/goform/formiPhoneAppPower.xml?1+PowerOn
http://<receiver-ip>/goform/formiPhoneAppPower.xml?1+PowerStandby

http://<receiver-ip>/goform/formiPhoneAppFavorite_Call.xml?01

http://<receiver-ip>/goform/formiPhoneAppTone_Status.xml
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PWON
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PWSTANDBY
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PW?
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MVUP
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MVUP
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MVDOWN
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MV05 ((TAKE CAUTION !!))
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MV?
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MUON
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?MUOFF
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?SITUNER
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?SIUSB
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?SIAUX1
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?SIIRADIO
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?TFAN104.100
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?TPAN01
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSTONE CTRL ON
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSTONE CTRL OFF
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSBAS UP
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSBAS DOWN
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSTRE UP
http://<receiver-ip>/goform/formiPhoneAppDirect.xml?PSTRE DOWN
http://<receiver-ip>/goform/formiPhoneAppControlJudge.xml
http://<receiver-ip>/NetAudio/art.asp-jpg?1630075616

http://<receiver-ip>:8080/description.xml
http://<receiver-ip>:8080/RenderingControl/desc.xml
http://<receiver-ip>:8080/AVTransport/desc.xml
http://<receiver-ip>/goform/AppCommand.xml

http://<receiver-ip>/goform/AppCommand.xml
  <?xml version="1.0" encoding="utf-8"?>
  <tx>
   <cmd id="1">GetAllZonePowerStatus</cmd>
   <cmd id="1">GetVolumeLevel</cmd>
   <cmd id="1">GetMuteStatus</cmd>
   <cmd id="1">GetSourceStatus</cmd>
   <cmd id="1">GetNetAudioStatus</cmd>
   <cmd id="1">GetZoneName</cmd>
   <cmd id="1">GetRenameSource</cmd>
   <cmd id="1">GetDeletedSource</cmd>
   <cmd id="1">GetDeletedNetworkSource</cmd>
   <cmd id="1">GetSystemFavoriteList</cmd>
   <cmd id="1">GetSurroundModeStatus</cmd>
   <cmd id="1">GetRestorerModeStatus</cmd>
  </tx>
  
http://<receiver-ip>/goform/AppCommand.xml
<?xml version="1.0" encoding="utf-8"?>
<tx>
   <cmd id="1">SetAddToSystemFavorite</cmd>
   <value>24</value>
</tx>


http://<receiver-ip>/goform/AppCommand.xml
<?xml version="1.0" encoding="utf-8"?>
<tx>
   <cmd id="1">SetAddToSystemFavorite</cmd>
   <zone>Main</zone>
   <value>24</value>
</tx>

http://<receiver-ip>/goform/AppCommand.xml
<tx>
    <cmd id="1">SetvTunerPlay</cmd>
    <title>Radio Station Name</title>
    <url>http://1.2.3.4:8080/;stream.mp3</url>
    <mime>MP3</mime>
</tx>'

http://<receiver-ip>/MainZone/index.put.asp?cmd0=<COMMAND>
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutMasterVolumeBtn/%3C
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutMasterVolumeBtn/%3E
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutMasterVolumeSet/-45.0  (TAKE CAUTION !!)
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutZone_InputFunction%2FSAT%2FCBL
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutZone_InputFunction%2FCD
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutZone_OnOff/ON
http://<receiver-ip>/MainZone/index.put.asp?cmd0=PutZone_OnOff/OFF

```
