import logging
from gui import VoxGUI
from assistant_controller import AssistantController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

app = VoxGUI()
controller = AssistantController(app)

app.set_listen_callback(controller.start_listening)
app.set_text_callback(controller.handle_text_input)

app.run()
