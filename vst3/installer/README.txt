TRICERATOPS — LOCAL DEBUG PACKAGE

Double-click Install.cmd.

The installer adds:
  - Triceratops VST3 to the current user's standard VST3 directory.
  - Triceratops Standalone to the Start menu.

This debug package reuses the existing Triceratops/Text2Score Agent backend in
WSL. It does not include the large model weights or training data. A later
distribution build can bundle the same backend and model without replacing the
Agent logic.
