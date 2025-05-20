# --- START OF FILE main.py ---

import asyncio
import signal as os_signal # برای مدیریت سیگنال‌ها به صورت سازگار
from telegram import Update, __version__ as TG_VER, Bot as TelegramBot
try:
    from telegram.ext import __version__ as PTB_VER
except ImportError:
    PTB_VER = TG_VER

from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          ContextTypes, ConversationHandler,
                          ApplicationBuilder, CallbackQueryHandler)
from aiohttp import web

# Import از config.py (مطمئن شوید config.py هم مطابق با آخرین اصلاحات است)
from config import (TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
                    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER,
                    DELETE_SINGER, REMOVE_LIST_CONFIRM,
                    CONFIRM_SINGER_SUGGESTION, CONFIRM_DELETE_HISTORY,
                    PORT, WEBHOOK_DOMAIN)

# Import ماژول‌های دیگر پروژه شما
from database.user_db import DatabaseHandler
from database.track_db import TrackDatabaseHandler
from services.user_manager import UserManager
from services.music_fetcher import MusicFetcher
from services.track_searcher import TrackSearcher
from handlers import command_handlers, menu_handlers, job_handlers
# از handlers.helper_handlers و utils.* استفاده نشده، اگر لازم است import کنید


class MusicBot:
    def __init__(self, token: str):
        self.token = token
        self.application: Application | None = None
        self.manual_request_queue: asyncio.Queue | None = None
        self.aiohttp_runner: web.AppRunner | None = None
        self.manual_request_worker_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event() # رویداد برای کنترل حلقه اصلی و خاموش شدن
        logger.info(f"MusicBot instance CREATED. PTB Version: {PTB_VER}")

    def _signal_handler(self, signum, frame):
        """Handles OS signals for graceful shutdown."""
        logger.info(f"OS Signal {signum} received. Setting stop event for graceful shutdown.")
        if not self._stop_event.is_set():
            # بهترین کار این است که event را از طریق loop اصلی set کنیم
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(self._stop_event.set)
            else: # اگر لوپ در حال اجرا نیست (مثلا در خطای اولیه یا قبل از start)
                self._stop_event.set()


    async def _initialize_bot_dependencies(self):
        logger.info(">>>>>>>> _initialize_bot_dependencies: ENTERED <<<<<<<<")
        if not self.application:
            logger.critical("_initialize_bot_dependencies: Application is not initialized. Cannot proceed.")
            return
        try:
            logger.info("_initialize_bot_dependencies: Initializing database handlers...")
            user_db = DatabaseHandler(DB_NAME)
            track_db = TrackDatabaseHandler(TRACK_DB_NAME)
            self.application.bot_data['user_db_handler'] = user_db
            self.application.bot_data['track_db_handler'] = track_db
            logger.info("_initialize_bot_dependencies: Database handlers ADDED to bot_data.")

            logger.info("_initialize_bot_dependencies: Fetching and caching all singer names...")
            all_singer_names_set = await track_db.get_all_unique_singer_names()
            self.application.bot_data['all_singer_names_list'] = list(all_singer_names_set)
            logger.info(f"_initialize_bot_dependencies: Stored {len(all_singer_names_set)} unique singer names in bot_data.")

            logger.info("_initialize_bot_dependencies: Initializing services...")
            user_manager = UserManager(user_db)
            music_fetcher = MusicFetcher()
            track_searcher = TrackSearcher(track_db)
            self.application.bot_data['user_manager'] = user_manager
            self.application.bot_data['music_fetcher'] = music_fetcher
            self.application.bot_data['track_searcher'] = track_searcher
            logger.info("_initialize_bot_dependencies: Core services ADDED to bot_data.")

            logger.info("_initialize_bot_dependencies: Initializing manual request queue and worker...")
            self.manual_request_queue = asyncio.Queue()
            self.application.bot_data['manual_request_queue'] = self.manual_request_queue
            self.manual_request_worker_task = asyncio.create_task(
                menu_handlers.manual_request_worker(self.application)
            )
            logger.info("_initialize_bot_dependencies: Manual request queue and worker task STARTED.")

            if not self.application.job_queue:
                 logger.warning("_initialize_bot_dependencies: JobQueue is not yet available from application object.")

        except Exception as e_deps:
            logger.critical(f">>>>>>>> _initialize_bot_dependencies: EXCEPTION occurred: {e_deps} <<<<<<<<", exc_info=True)
            raise
        logger.info(">>>>>>>> _initialize_bot_dependencies: EXITED SUCCESSFULLY <<<<<<<<")

    def _setup_handlers(self):
        logger.info("_setup_handlers: Configuring all handlers...")
        main_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", command_handlers.start_command)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['list']}$"), menu_handlers.list_menu_prompt_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['receive_music_now']}$"), menu_handlers.receive_music_now_handler),
                ],
                LIST_MENU: [MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['edit_list']}|{KEYBOARD_TEXTS['remove_list']}|{KEYBOARD_TEXTS['back']})$"), menu_handlers.list_menu_router)],
                EDIT_LIST_MENU: [MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['add']}|{KEYBOARD_TEXTS['delete']}|{KEYBOARD_TEXTS['back']})$"), menu_handlers.edit_list_menu_router)],
                ADD_SINGER: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['delete']}$"), menu_handlers.ignore_delete_in_add_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['delete']})$"), menu_handlers.save_singer_handler),
                ],
                CONFIRM_SINGER_SUGGESTION: [
                    CallbackQueryHandler(menu_handlers.singer_suggestion_callback_handler, pattern="^suggest_"),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_add_singer_from_suggestion),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handlers.fallback_text_in_suggestion_state)
                ],
                DELETE_SINGER: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['add']}$"), menu_handlers.ignore_add_in_delete_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['add']})$"), menu_handlers.remove_singer_handler),
                ],
                REMOVE_LIST_CONFIRM: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['confirm']}$"), menu_handlers.confirm_remove_list_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['cancel_action']}$"), menu_handlers.cancel_remove_list_handler),
                ],
            },
            fallbacks=[CommandHandler("cancel", command_handlers.cancel_command)],
            name="main_menu_conversation", persistent=False
        )
        if self.application:
            self.application.add_handler(main_conv_handler)
            logger.info("_setup_handlers: Main Conversation handler ADDED.")

        delete_history_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("delete_history", command_handlers.delete_history_prompt_command)],
            states={CONFIRM_DELETE_HISTORY: [CallbackQueryHandler(command_handlers.delete_history_confirmation_callback, pattern="^history_delete_confirm_")]},
            fallbacks=[CommandHandler("cancel", command_handlers.cancel_command)],
            name="delete_history_conversation", persistent=False, per_user=True, per_chat=True
        )
        if self.application:
            self.application.add_handler(delete_history_conv_handler)
            logger.info("_setup_handlers: Delete Sent Music History Conversation handler ADDED.")

    def _schedule_bot_jobs(self, job_queue):
        logger.info("_schedule_bot_jobs: Scheduling...")
        if job_queue:
            job_queue.run_repeating(job_handlers.run_music_processing_job, interval=86000, first=0, name="MusicDataProcessingJob")
            logger.info("_schedule_bot_jobs: Music data processing job SCHEDULED.")
            job_queue.run_repeating(job_handlers.run_user_notification_job, interval=86900, first=0, name="DailyUserNotificationJob")
            logger.info("_schedule_bot_jobs: Daily user notification job SCHEDULED.")
        else:
            logger.error("_schedule_bot_jobs: JobQueue not available. Jobs cannot be scheduled.")

    async def shutdown_manual_worker(self):
        logger.info("shutdown_manual_worker: Attempting to shutdown manual worker...")
        if self.manual_request_queue and self.manual_request_worker_task and not self.manual_request_worker_task.done():
            logger.info("shutdown_manual_worker: Queue is empty or worker will stop after current item, putting None to stop worker.")
            await self.manual_request_queue.put(None) # Signal worker to stop

        if self.manual_request_worker_task:
            if not self.manual_request_worker_task.done():
                logger.info("shutdown_manual_worker: Waiting for worker task to finish (max 10s)...")
                try:
                    await asyncio.wait_for(self.manual_request_worker_task, timeout=10.0)
                    logger.info("shutdown_manual_worker: Worker task finished gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("shutdown_manual_worker: Worker task did not shut down gracefully in time. Cancelling.")
                    self.manual_request_worker_task.cancel()
                    try:
                        await self.manual_request_worker_task
                    except asyncio.CancelledError:
                        logger.info("shutdown_manual_worker: Worker task cancellation confirmed.")
                except Exception as e_wait: # Catch other exceptions during wait
                    logger.error(f"shutdown_manual_worker: Error during worker task wait: {e_wait}")
            else:
                logger.info("shutdown_manual_worker: Worker task already done.")
        else:
            logger.info("shutdown_manual_worker: No worker task to shut down.")


    async def _handle_telegram_webhook(self, request: web.Request) -> web.Response:
        logger.debug(f"Webhook received a request. Method: {request.method}")
        if request.method == "POST":
            try:
                update_json = await request.json()
                update = Update.de_json(update_json)
                if self.application:
                    await self.application.process_update(update)
                    return web.Response(text="OK", status=200)
                else:
                    logger.error("Application object is None in webhook handler.")
                    return web.Response(text="Internal Server Error", status=500)
            except Exception as e:
                logger.error(f"Error processing webhook update: {e}", exc_info=True)
                return web.Response(text="Error processing update", status=500)
        return web.Response(text="Only POST requests are allowed", status=405)

    async def _health_check(self, request: web.Request) -> web.Response:
        logger.debug("Health check endpoint was pinged.")
        return web.Response(text="MusicBot is alive! (Webhook mode enforced)", status=200)

    async def run(self):
        logger.info(f"run: Attempting to start bot with token: {'***' + self.token[-6:] if self.token and len(self.token) > 6 else 'TOKEN_NOT_SET_OR_TOO_SHORT'}")

        if not self.token or self.token == "YOUR_BOT_TOKEN_HERE": # TOKEN از config.py
            logger.critical("run: Bot TOKEN is not set or is default. Aborting.")
            return

        if not WEBHOOK_DOMAIN: # WEBHOOK_DOMAIN از config.py
            logger.critical("run: WEBHOOK_DOMAIN is not set in config. Aborting webhook setup.")
            return

        # --- Setup OS Signal Handlers ---
        # این کار را قبل از ایجاد loop یا اجرای هر تسک طولانی انجام می‌دهیم
        loop = asyncio.get_event_loop()
        try:
            # loop.add_signal_handler فقط در Unix و پایتون 3.8+ (تقریبا) به خوبی کار میکند
            # و باید در ترد اصلی و قبل از اینکه loop.run_forever() یا مشابه آن صدا زده شود، ثبت شود.
            for sig in (os_signal.SIGINT, os_signal.SIGTERM):
                loop.add_signal_handler(sig, self._signal_handler, sig, None)
            logger.info("OS signal handlers (SIGINT, SIGTERM) registered using loop.add_signal_handler.")
        except (NotImplementedError, AttributeError, RuntimeError) as e_signal_loop:
            # NotImplementedError: در ویندوز
            # AttributeError: اگر loop.add_signal_handler وجود نداشته باشد (بسیار بعید در پایتون مدرن)
            # RuntimeError: اگر در تردی غیر از ترد اصلی هستیم یا loop در حال اجراست
            logger.warning(f"Could not set signal handlers using loop.add_signal_handler: {e_signal_loop}. "
                           "Falling back to os.signal.signal (less ideal for asyncio).")
            try:
                for sig in (os_signal.SIGINT, os_signal.SIGTERM):
                    os_signal.signal(sig, self._signal_handler)
                logger.info("OS signal handlers (SIGINT, SIGTERM) registered using os.signal.signal.")
            except (ValueError, OSError, RuntimeError) as e_signal_os: # ValueError اگر در ترد غیر اصلی
                logger.error(f"Failed to set OS signal handlers using os.signal.signal: {e_signal_os}. "
                             "Graceful shutdown via OS signals might not work reliably.")

        try:
            logger.info("run: Building application...")
            self.application = ApplicationBuilder().token(self.token).build()
            logger.info("run: Application BUILT.")

            logger.info("run: Initializing application (native initialize)...")
            await self.application.initialize()
            logger.info("run: Application NATIVELY INITIALIZED.")

            logger.info("run: Manually initializing bot dependencies...")
            await self._initialize_bot_dependencies()
            logger.info("run: Bot dependencies INITIALIZED.")

            logger.info("run: Setting up handlers...")
            self._setup_handlers()
            logger.info("run: Handlers SET UP.")

            webhook_path = f"/{self.token}"
            web_server_app = web.Application()
            web_server_app.router.add_post(webhook_path, self._handle_telegram_webhook)
            web_server_app.router.add_get("/", self._health_check)

            self.aiohttp_runner = web.AppRunner(web_server_app)
            await self.aiohttp_runner.setup()
            site = web.TCPSite(self.aiohttp_runner, host="0.0.0.0", port=PORT)
            await site.start()
            logger.info(f"Web server started on 0.0.0.0:{PORT}. Health check on '/', Webhook on '{webhook_path}'")

            full_webhook_url = f"https://{WEBHOOK_DOMAIN}{webhook_path}"
            logger.info(f"run: Attempting to set webhook to: {full_webhook_url}")
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("run: Attempted to delete any existing webhook.")
                await self.application.bot.set_webhook(url=full_webhook_url, allowed_updates=Update.ALL_TYPES)
                logger.info("run: >>>>>>> Webhook SET successfully! Bot should be operational. <<<<<<<")
            except Exception as e_webhook:
                logger.critical(f"run: FAILED to set webhook: {e_webhook}. Bot will likely not work.", exc_info=True)
                self._stop_event.set() # باعث خروج از حلقه اصلی می‌شود

            if self.application.job_queue:
                self._schedule_bot_jobs(self.application.job_queue)
            else:
                logger.error("run: JobQueue is not available. Jobs cannot be scheduled.")

            logger.info("run: Starting application (dispatcher)...")
            await self.application.start()
            logger.info("run: Application dispatcher STARTED.")

            if not self._stop_event.is_set(): # اگر خطایی در تنظیم وب‌هوک رخ نداده باشد
                logger.info(f"run: Bot is ALIVE and listening for webhook updates on {full_webhook_url}")
                logger.info(f"run: Health check available at https://{WEBHOOK_DOMAIN}/")
            else:
                logger.warning("run: Stop event was set before entering main loop (likely due to webhook setup failure).")

            # حلقه اصلی برای زنده نگه داشتن برنامه تا زمانی که سیگنال خاموش شدن دریافت شود
            await self._stop_event.wait()
            logger.info("run: Stop event received OR error occurred, initiating shutdown sequence...")

        except (KeyboardInterrupt, SystemExit) as sig_ex: # اینها دیگر نباید مستقیم به اینجا برسند اگر سیگنال‌ها درست کار کنند
            logger.info(f"run: Bot shutdown signal ({type(sig_ex).__name__}) directly caught in run. Setting stop event.")
            self._stop_event.set()
        except Exception as e:
            logger.critical(f"run: Unhandled CRITICAL exception during run: {e}", exc_info=True)
            self._stop_event.set() # در صورت بروز خطای ناشناخته، برنامه را متوقف کن
        finally:
            logger.info("run: Initiating FINALLY block for graceful shutdown...")

            if self.application and self.application.running:
                logger.info("run: Stopping PTB application dispatcher...")
                await self.application.stop()

            await self.shutdown_manual_worker() # باید قبل از shutdown اپلیکیشن باشد

            if self.application:
                logger.info("run: Shutting down PTB application...")
                await self.application.shutdown()

            if self.aiohttp_runner:
                logger.info("run: Cleaning up aiohttp web server...")
                await self.aiohttp_runner.cleanup()

            # حذف وب‌هوک در انتها (این کار اختیاری است اما می‌تواند خوب باشد)
            if self.application and self.application.bot and WEBHOOK_DOMAIN:
                try:
                    logger.info("run: Final attempt to delete webhook...")
                    # یک شی Bot جدید می‌سازیم چون application ممکن است shutdown شده باشد
                    # هرچند self.application.bot باید هنوز در دسترس باشد اگر اپلیکیشن درست shutdown شود
                    temp_bot = TelegramBot(token=self.token)
                    await temp_bot.delete_webhook(drop_pending_updates=True)
                    await temp_bot.shutdown() # بستن سشن‌های http موقت Bot
                    logger.info("run: Webhook DELETED (final attempt).")
                except Exception as e_wh_del_final:
                    logger.error(f"run: Error deleting webhook during final shutdown: {e_wh_del_final}")

            logger.info("run: MusicBot application SHUT DOWN sequence complete.")


def main() -> None:
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("main: TOKEN is not available or is default. Exiting.")
        return
    if not WEBHOOK_DOMAIN:
        logger.critical("main: WEBHOOK_DOMAIN is not set. Exiting.")
        return

    logger.info("main: Creating MusicBot instance (Webhook mode enforced)...")
    bot_instance = MusicBot(token=TOKEN)

    # asyncio.run() برای اجرای تابع اصلی async و مدیریت loop
    # این روش مدرن‌تر از get_event_loop() و run_until_complete() است.
    try:
        asyncio.run(bot_instance.run())
    except KeyboardInterrupt: # این باید توسط signal_handler داخل run گرفته شود
        logger.info("main: KeyboardInterrupt caught by asyncio.run wrapper (should have been handled internally).")
    except Exception as e_main_run:
        logger.critical(f"main: Unhandled critical error in asyncio.run(bot_instance.run()): {e_main_run}", exc_info=True)
    finally:
        logger.info("main: Main function finished.")


if __name__ == "__main__":
    # لاگر باید در config.py قبل از هر چیز دیگری مقداردهی اولیه شود
    logger.info(f"__main__: Script starting (PTB Version: {PTB_VER}).")
    main()
    logger.info("__main__: Script finished executing main().")

# --- END OF FILE main.py ---