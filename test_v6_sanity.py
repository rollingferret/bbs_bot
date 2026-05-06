import logging
from bbs_bot_v6 import BBSBot, BotConfiguration
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SanityCheck")


def test_v6_sanity():
    logger.info("Initializing V6 Bot...")
    config = BotConfiguration()
    bot = BBSBot(config=config)

    # Create a fake blank snapshot to pass to the handlers
    fake_snapshot = Image.new("RGB", (1920, 1080), color="black")
    bot.snapshot = fake_snapshot
    bot.region = (0, 0, 1920, 1080)

    # Override smart_click and find_image to prevent actual X11 calls and timeouts
    bot.smart_click = lambda *args, **kwargs: True
    bot.find_image = lambda *args, **kwargs: None
    bot.find_all = lambda *args, **kwargs: []
    bot._send_x11_click = lambda *args, **kwargs: True

    logger.info("Testing handle_menu...")
    try:
        bot.handle_menu(haystack=bot.snapshot)
        logger.info("handle_menu passed!")
    except Exception as e:
        logger.error(f"handle_menu failed: {e}")

    logger.info("Testing handle_enter_room_list...")
    try:
        bot.handle_enter_room_list(haystack=bot.snapshot)
        logger.info("handle_enter_room_list passed!")
    except Exception as e:
        logger.error(f"handle_enter_room_list failed: {e}")

    logger.info("Testing handle_scan_rooms...")
    try:
        bot._force_refresh = True
        bot.handle_scan_rooms(haystack=bot.snapshot)
        logger.info("handle_scan_rooms passed!")
    except Exception as e:
        logger.error(f"handle_scan_rooms failed: {e}")

    logger.info("Testing handle_ready...")
    try:
        bot.handle_ready(haystack=bot.snapshot)
        logger.info("handle_ready passed!")
    except Exception as e:
        logger.error(f"handle_ready failed: {e}")

    logger.info("Testing handle_check_run_start...")
    try:
        bot.handle_check_run_start(haystack=bot.snapshot)
        logger.info("handle_check_run_start passed!")
    except Exception as e:
        logger.error(f"handle_check_run_start failed: {e}")

    logger.info("Testing handle_running...")
    try:
        bot.handle_running(haystack=bot.snapshot)
        logger.info("handle_running passed!")
    except Exception as e:
        logger.error(f"handle_running failed: {e}")

    logger.info("Testing handle_finish...")
    try:
        bot.handle_finish(haystack=bot.snapshot)
        logger.info("handle_finish passed!")
    except Exception as e:
        logger.error(f"handle_finish failed: {e}")

    logger.info("Testing handle_distraction...")
    try:
        # Avoid the random sleep in testing
        bot.config.DISTRACTION_DURATION = (0, 0)
        bot.handle_distraction(haystack=bot.snapshot)
        logger.info("handle_distraction passed!")
    except Exception as e:
        logger.error(f"handle_distraction failed: {e}")

    logger.info("Testing check_circadian_rhythm...")
    try:
        bot.next_profile_swap = 0  # Force a swap
        bot.check_circadian_rhythm()
        logger.info("check_circadian_rhythm passed!")
    except Exception as e:
        logger.error(f"check_circadian_rhythm failed: {e}")


if __name__ == "__main__":
    test_v6_sanity()
