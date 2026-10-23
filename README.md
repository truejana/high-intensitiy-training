# HIT Training Android

Kivy-Port der Tkinter-Version 1.1. Android-APK wird per GitHub Actions gebaut.

## Installation
Alle Dateien einschließlich `.github/workflows/android.yml` in das Repository hochladen. Unter **Actions → Android APK → Run workflow** den Build starten. Danach das Artefakt **HIT-Training-APK** herunterladen und entpacken.

**Hinweise:** Der Android-Build wurde hier nicht ausgeführt und ist noch nicht auf einem Gerät getestet. Die Datenbank liegt im privaten App-Datenordner. CSV-Export und Sicherung werden derzeit ebenfalls dort abgelegt und sind möglicherweise nicht über einen normalen Dateimanager zugänglich. Die bisherige Pydroid-Datenbank wird nicht automatisch importiert. Löschen von Übungen/Sätzen erfolgt in diesem Prototyp ohne Rückfrage.
