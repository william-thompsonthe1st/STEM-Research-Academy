# LARP scout drive firmware

This package runs the differential-drive controller on each LARP scout's ECHO
board. Flash `larp_scout_controller.ino` with `ROBOT_ID = 'A'` or `ROBOT_ID =
'B'`. It joins `3TSahur-Swarm`, reports a heartbeat to the 3TSahur hub, serves
`/drive`, `/stop`, and `/status`, and stops motors after 500 ms without a valid
command.

The LARP drive controller and its separate Inland ESP32-CAM must use the same
`A` or `B` identity. Confirm the ECHO motor IDs and direction with wheels
raised before ground operation.
