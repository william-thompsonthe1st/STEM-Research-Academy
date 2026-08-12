# 3TSahur hub server

`robot_server` is the Python package that runs on the Raspberry Pi 4. It serves
the control dashboard, captures the Logitech C270, mixes mecanum commands into
four PWM motor outputs, and proxies commands/status for LARP Scouts A and B.

Run it locally with `python -m robot_server.app` after installing
`requirements.txt`. Without `RPi.GPIO`, motor commands run in simulation mode;
the API and dashboard remain available. Production deployment is performed by
the repository's installer, not by launching the development server manually.

Hardware pin mapping and safety checks: [../docs/WIRING.md](../docs/WIRING.md).
