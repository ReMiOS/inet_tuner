# iNET Tuner
Denon / Marantz Receiver - Internet Radiostream Favorite editor making use op REST-API commands.
Simple tool to edit internet radio stream favorites on Denon and Marantz receivers and streamers.

Database scheme based on [YTuner](https://github.com/coffeegreg/YTuner) 
and updates from [Radio-Browser](https://api.radio-browser.info/)

Tested on Denon DNP-F109

! Use at own risk !

# Screenshot
![iNET_Tuner](img/inet_tuner.png)  

# Denon REST-API commands

There is no known documentation about this REST-API from Denon.
Depending on your model they can work (tested on Denon DNP F109)
For instance the formiPhoneAppDirect.xml ENDPOINT seems unavailable on Denon AVR X1300W

```
http://<ip-address>/goform/Deviceinfo.xml
http://<ip-address>/goform/formNetAudio_StatusXml.xml

http://<ip-address>/goform/formiPhoneAppPower.xml?1+PowerOn
http://<ip-address>/goform/formiPhoneAppPower.xml?1+PowerStandby

http://<ip-address>/goform/formiPhoneAppFavorite_Call.xml?01

http://<ip-address>/goform/formiPhoneAppDirect.xml?PWON
http://<ip-address>/goform/formiPhoneAppDirect.xml?PWSTANDBY
http://<ip-address>/goform/formiPhoneAppDirect.xml?MVUP
http://<ip-address>/goform/formiPhoneAppDirect.xml?MVUP
http://<ip-address>/goform/formiPhoneAppDirect.xml?MVDOWN
http://<ip-address>/goform/formiPhoneAppDirect.xml?MV05
http://<ip-address>/goform/formiPhoneAppDirect.xml?MUON
http://<ip-address>/goform/formiPhoneAppDirect.xml?MUOFF
http://<ip-address>/goform/formiPhoneAppDirect.xml?SITUNER
http://<ip-address>/goform/formiPhoneAppDirect.xml?SIUSB
http://<ip-address>/goform/formiPhoneAppDirect.xml?SIAUX1
http://<ip-address>/goform/formiPhoneAppDirect.xml?SIIRADIO
http://<ip-address>/goform/formiPhoneAppDirect.xml?TFAN104.100
http://<ip-address>/goform/formiPhoneAppDirect.xml?TPAN01
http://<ip-address>/goform/formiPhoneAppControlJudge.xml
http://<ip-address>/NetAudio/art.asp-jpg?1630075616

http://<ip-address>:8080/description.xml
http://<ip-address>:8080/RenderingControl/desc.xml
http://<ip-address>:8080/AVTransport/desc.xml
http://<ip-address>/goform/AppCommand.xml

http://<ip-address>/goform/AppCommand.xml
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
  </tx>
  
http://<ip-address>/goform/AppCommand.xml
<?xml version="1.0" encoding="utf-8"?>
<tx>
   <cmd id="1">SetAddToSystemFavorite</cmd>
   <value>24</value>
</tx>

http://<ip-address>/goform/AppCommand.xml
<tx>
    <cmd id="1">SetvTunerPlay</cmd>
    <title>Radio Station Name</title>
    <url>http://1.2.3.4:8080/;stream.mp3</url>
    <mime>MP3</mime>
</tx>'

```
