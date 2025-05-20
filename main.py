# --- START OF FILE main.py ---

from telegram import Update, __version__ as TG_VER
try:
    from telegram.ext import __version__ as PTB_VER
except ImportError:
    PTB_VER = TG_VER

from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          ContextTypes, ConversationHandler,
                          ApplicationBuilder, CallbackQueryHandler)
import asyncio
from aiohttp import web
from config import (TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
                    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER,
                    DELETE_SINGER, REMOVE_LIST_CONFIRM,
                    CONFIRM_SINGER_SUGGESTION, CONFIRM_DELETE_HISTORY,
                    PORT, WEBHOOK_DOMAIN) # APP_ENV دیگر اینجا خوانده نمی‌شود

import telegram

from database.user_db import DatabaseHandler
from database.track_db import TrackDatabaseHandler
from services.user_manager import UserManager
from services.music_fetcher import MusicFetcher
from services.track_searcher import TrackSearcher
from handlers import command_handlers
from handlers import menu_handlers
from handlers import job_handlers


class MusicBot:
    def __init__(self, token: str):
        self.token = token
        self.application: Application | None = None
        self.manual_request_queue: asyncio.Queue | None = None
        self.aiohttp_runner: web.AppRunner | None = None
        self.manual_request_worker_task: asyncio.Task | None = None
        logger.info(f"MusicBot instance CREATED. PTB Version: {PTB_VER}") # APP_ENV از لاگ حذف شد

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
        # ... (کد کامل _setup_handlers شما بدون تغییر باقی می‌ماند) ...
        main_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", command_handlers.start_command)
            ],
            states={
                MAIN_MENU: [
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['list']}$"),
                        menu_handlers.list_menu_prompt_handler),
                    MessageHandler(
                        filters.Regex(
                            f"^{KEYBOARD_TEXTS['receive_music_now']}$"),
                        menu_handlers.receive_music_now_handler),
                ],
                LIST_MENU: [
                    MessageHandler(
                        filters.Regex(
                            f"^({KEYBOARD_TEXTS['edit_list']}|{KEYBOARD_TEXTS['remove_list']}|{KEYBOARD_TEXTS['back']})$"
                        ), menu_handlers.list_menu_router),
                ],
                EDIT_LIST_MENU: [
                    MessageHandler(
                        filters.Regex(
                            f"^({KEYBOARD_TEXTS['add']}|{KEYBOARD_TEXTS['delete']}|{KEYBOARD_TEXTS['back']})$"
                        ), menu_handlers.edit_list_menu_router),
                ],
                ADD_SINGER: [
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"),
                        menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['delete']}$"),
                        menu_handlers.ignore_delete_in_add_handler),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & ~filters.Regex(
                            f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['delete']})$"
                        ), menu_handlers.save_singer_handler),
                ],
                CONFIRM_SINGER_SUGGESTION: [
                    CallbackQueryHandler(
                        menu_handlers.singer_suggestion_callback_handler,
                        pattern="^suggest_"),
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"),
                        menu_handlers.back_to_add_singer_from_suggestion),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        menu_handlers.fallback_text_in_suggestion_state)
                ],
                DELETE_SINGER: [
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"),
                        menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['add']}$"),
                                   menu_handlers.ignore_add_in_delete_handler),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & ~filters.Regex(
                            f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['add']})$"
                        ), menu_handlers.remove_singer_handler),
                ],
                REMOVE_LIST_CONFIRM: [
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['confirm']}$"),
                        menu_handlers.confirm_remove_list_handler),
                    MessageHandler(
                        filters.Regex(f"^{KEYBOARD_TEXTS['cancel_action']}$"),
                        menu_handlers.cancel_remove_list_handler),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", command_handlers.cancel_command)
            ],
            name="main_menu_conversation",
            persistent=False)

        if self.application:
            self.application.add_handler(main_conv_handler)
            logger.info("_setup_handlers: Main Conversation handler ADDED.")
        else:
            logger.error(
                "_setup_handlers: Application not initialized for Main Conversation handler."
            )
        delete_history_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("delete_history",
                               command_handlers.delete_history_prompt_command)
            ],
            states={
                CONFIRM_DELETE_HISTORY: [
                    CallbackQueryHandler(
                        command_handlers.delete_history_confirmation_callback,
                        pattern="^history_delete_confirm_")
                ]
            },
            fallbacks=[
                CommandHandler("cancel", command_handlers.cancel_command)
            ],
            name="delete_history_conversation",
            persistent=False,
            per_user=True,
            per_chat=True
        )

        if self.application:
            self.application.add_handler(delete_history_conv_handler)
            logger.info(
                "_setup_handlers: Delete Sent Music History Conversation handler ADDED."
            )
        else:
            logger.error(
                "_setup_handlers: Application not initialized for Delete History Conversation handler."
            )


    def _schedule_bot_jobs(self, job_queue):
        # ... (کد کامل _schedule_bot_jobs شما بدون تغییر باقی می‌ماند) ...
        logger.info("_schedule_bot_jobs: Scheduling...")
        if job_queue:
            job_queue.run_repeating(job_handlers.run_music_processing_job, interval=86000, first=60, name="MusicDataProcessingJob")
            logger.info("_schedule_bot_jobs: Music data processing job SCHEDULED.")
            job_queue.run_repeating(job_handlers.run_user_notification_job, interval=86900, first=120, name="DailyUserNotificationJob")
            logger.info("_schedule_bot_jobs: Daily user notification job SCHEDULED.")
        else:
            logger.error("_schedule_bot_jobs: JobQueue not available. Jobs cannot be scheduled.")


    async def shutdown_manual_worker(self):
        # ... (کد کامل shutdown_manual_worker شما بدون تغییر باقی می‌ماند) ...
        logger.info(
            "shutdown_manual_worker: Attempting to shutdown manual worker...")
        if self.manual_request_queue and self.manual_request_worker_task and not self.manual_request_worker_task.done(
        ):
            if self.manual_request_queue.empty():
                logger.info(
                    "shutdown_manual_worker: Queue is empty, putting None to stop worker."
                )
                await self.manual_request_queue.put(None)
            else:
                logger.warning(
                    "shutdown_manual_worker: Manual request queue is not empty. Worker will process items then stop if None is next."
                )
                await self.manual_request_queue.put(None)

        if self.manual_request_worker_task:
            if self.manual_request_worker_task.done():
                logger.info(
                    "shutdown_manual_worker: Worker task already done.")
            else:
                logger.info(
                    "shutdown_manual_worker: Waiting for worker task to finish (max 10s)..."
                )
                try:
                    await asyncio.wait_for(self.manual_request_worker_task,
                                           timeout=10.0)
                    logger.info(
                        "shutdown_manual_worker: Worker task finished gracefully."
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "shutdown_manual_worker: Worker task did not shut down gracefully in time. Cancelling."
                    )
                    self.manual_request_worker_task.cancel()
                    try:
                        await self.manual_request_worker_task
                    except asyncio.CancelledError:
                        logger.info(
                            "shutdown_manual_worker: Worker task cancellation confirmed."
                        )
                    except Exception as e_cancel:
                        logger.error(
                            f"shutdown_manual_worker: Error during worker task cancellation: {e_cancel}"
                        )
                except Exception as e_wait:
                    logger.error(
                        f"shutdown_manual_worker: Error during worker task wait: {e_wait}"
                    )
        else:
            logger.info("shutdown_manual_worker: No worker task to shut down.")

    async def _handle_telegram_webhook(self, request: web.Request) -> web.Response:
        # ... (کد کامل _handle_telegram_webhook شما بدون تغییر باقی می‌ماند) ...
        logger.debug(f"Webhook received a request. Method: {request.method}")
        if request.method == "POST":
            try:
                update_json = await request.json()
                update = Update.de_json(update_json)

                if self.application:
                    await self.application.process_update(update)
                    logger.debug("Webhook update processed via application.process_update().")
                    return web.Response(text="OK", status=200)
                else:
                    logger.error("Application object is None in webhook handler. Cannot process update.")
                    return web.Response(text="Internal Server Error: Application not ready", status=500)
            except Exception as e:
                logger.error(f"Error processing webhook update: {e}", exc_info=True)
                return web.Response(text="Error processing update", status=500)
        logger.warning(f"Webhook received non-POST request: {request.method}")
        return web.Response(text="Only POST requests are allowed", status=405)


    async def _health_check(self, request: web.Request) -> web.Response:
        # ... (کد کامل _health_check شما بدون تغییر باقی می‌ماند) ...
        logger.debug("Health check endpoint was pinged.")
        return web.Response(text=f"MusicBot is alive! (Webhook mode enforced)", status=200) # پیام تغییر کرد


    async def run(self):
        logger.info(f"run: Attempting to start bot with token: {'***' + self.token[-6:] if self.token and len(self.token) > 6 else 'TOKEN_NOT_SET_OR_TOO_SHORT'}")

        if not self.token or TOKEN == "YOUR_BOT_TOKEN_HERE": # بررسی TOKEN از config
            logger.critical("run: Bot TOKEN is not set or is default. Aborting.")
            return

        # WEBHOOK_DOMAIN حالا باید همیشه در config.py مقدار داشته باشد (یا برنامه قبلاً خارج شده)
        if not WEBHOOK_DOMAIN:
            logger.critical("run: WEBHOOK_DOMAIN is not set in config. Aborting webhook setup.")
            return # یا raise خطا

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
            logger.info(f"run: bot_data keys AFTER manual dependencies init: {list(self.application.bot_data.keys())}")

            logger.info("run: Setting up handlers...")
            self._setup_handlers()
            logger.info("run: Handlers SET UP.")

            webhook_path = f"/{self.token}"
            web_server = web.Application()
            web_server.router.add_post(webhook_path, self._handle_telegram_webhook)
            web_server.router.add_get("/", self._health_check) # Health check در روت اصلی

            self.aiohttp_runner = web.AppRunner(web_server)
            await self.aiohttp_runner.setup()
            site = web.TCPSite(self.aiohttp_runner, host="0.0.0.0", port=PORT)
            await site.start()
            logger.info(f"Web server started on 0.0.0.0:{PORT}. Health check on '/', Webhook on '{webhook_path}'")

            # --- تنظیم وب‌هوک (همیشه انجام می‌شود اگر WEBHOOK_DOMAIN موجود باشد) ---
            full_webhook_url = f"https://{WEBHOOK_DOMAIN}{webhook_path}"
            logger.info(f"run: Attempting to set webhook to: {full_webhook_url}")
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("run: Attempted to delete any existing webhook.")

                await self.application.bot.set_webhook(
                    url=full_webhook_url,
                    allowed_updates=Update.ALL_TYPES,
                )
                logger.info("run: >>>>>>> Webhook SET successfully! Bot should be operational. <<<<<<<")
            except telegram.error.BadRequest as e_bad_request:
                logger.critical(f"run: FAILED to set webhook (BadRequest): {e_bad_request}. Bot will likely not work. Check DNS and URL for {WEBHOOK_DOMAIN}.")
                # در این حالت، شاید بهتر باشد برنامه متوقف شود
                # raise # <--- برای توقف
            except Exception as e_webhook:
                logger.critical(f"run: An UNEXPECTED CRITICAL error occurred while setting webhook: {e_webhook}. Bot will likely not work.", exc_info=True)
                # raise # <--- برای توقف

            if self.application.job_queue:
                self._schedule_bot_jobs(self.application.job_queue)
            else:
                logger.error("run: JobQueue is not available after application.initialize(). Jobs cannot be scheduled.")

            logger.info("run: Starting application (dispatcher)...")
            await self.application.start()
            logger.info("run: Application dispatcher STARTED.")

            logger.info(f"run: Bot is ALIVE and listening for webhook updates on https://{WEBHOOK_DOMAIN}{webhook_path}")
            logger.info(f"run: Health check available at https://{WEBHOOK_DOMAIN}/")

            stop_event = asyncio.Event()
            loop = asyncio.get_event_loop()
            # استفاده از signal برای خاموش شدن صحیح (اگر پایتون >= 3.8/3.9)
            # این بخش را می‌توانید نگه دارید یا اگر در محیط Railway با آن مشکل دارید، موقتاً حذف کنید
            # و به Ctrl+C در لاگ‌ها یا دستور stop از Railway اکتفا کنید.
            # در لینوکس معمولاً کار می‌کند.
            import signal as os_signal
            def _signal_handler_main(signum, frame):
                logger.info(f"OS Signal {signum} received in main run, setting stop_event.")
                if not stop_event.is_set():
                    if loop.is_running():
                         loop.call_soon_threadsafe(stop_event.set)
                    else:
                        stop_event.set()
            try:
                loop.add_signal_handler(os_signal.SIGINT, lambda: _signal_handler_main(os_signal.SIGINT, None))
                loop.add_signal_handler(os_signal.SIGTERM, lambda: _signal_handler_main(os_signal.SIGTERM, None))
            except RuntimeError as e_signal_main:
                logger.warning(f"Could not add signal handlers directly in main run: {e_signal_main}")


            await stop_event.wait()
            logger.info("run: Stop event received, initiating shutdown sequence...")

        except (KeyboardInterrupt, SystemExit) as sig:
            logger.info(f"run: Bot shutdown signal received directly ({type(sig).__name__}).")
        except Exception as e:
            logger.critical(f"run: Unhandled CRITICAL exception during run: {e}", exc_info=True)
        finally:
            logger.info("run: Initiating FINALLY block for graceful shutdown...")

            if self.application and self.application.running:
                logger.info("run: Stopping PTB application dispatcher...")
                await self.application.stop()
            elif self.application and not self.application.running:
                 logger.info("run: PTB application was not running or already stopped.")

            await self.shutdown_manual_worker()

            if self.application: # دیگر نیازی به چک کردن .initialized نیست چون بعد از stop()، shutdown() همیشه باید صدا زده شود
                logger.info("run: Shutting down PTB application...")
                await self.application.shutdown()

            if self.aiohttp_runner:
                logger.info("run: Cleaning up aiohttp web server...")
                await self.aiohttp_runner.cleanup()
                logger.info("run: aiohttp web server CLEANED UP.")

            if self.application and self.application.bot and WEBHOOK_DOMAIN: # همیشه سعی در حذف وب‌هوک می‌کنیم
                try:
                    logger.info("run: Final attempt to delete webhook...")
                    temp_bot = telegram.Bot(token=self.token)
                    await temp_bot.delete_webhook(drop_pending_updates=True)
                    await temp_bot.shutdown()
                    logger.info("run: Webhook DELETED (final attempt).")
                except Exception as e_wh_del_final:
                    logger.error(f"run: Error deleting webhook during final shutdown: {e_wh_del_final}")

            logger.info("run: MusicBot application SHUT DOWN sequence complete.")


def main() -> None:
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("main: TOKEN is not available or is default (checked from config). Exiting.")
        return

    logger.info(f"main: Creating MusicBot instance (Webhook mode enforced)...") # پیام تغییر کرد
    bot_instance = MusicBot(token=TOKEN)

    loop = asyncio.get_event_loop()
    main_task = None
    try:
        logger.info("main: Starting bot_instance.run() within asyncio event loop...")
        main_task = loop.create_task(bot_instance.run())
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        logger.info("main: KeyboardInterrupt received by main().")
        if main_task and not main_task.done():
            logger.info("main: Cancelling main_task due to KeyboardInterrupt...")
            main_task.cancel()
            try:
                loop.run_until_complete(main_task)
            except asyncio.CancelledError:
                logger.info("main: Main task was cancelled successfully after KeyboardInterrupt.")
            except Exception as e_after_cancel:
                 logger.error(f"main: Exception after cancelling main_task: {e_after_cancel}", exc_info=True)
    except RuntimeError as e:
        if "cannot schedule new futures after shutdown" in str(e).lower() or \
           "Event loop is closed" in str(e).lower():
            logger.warning(f"main: Event loop was already shut down or closed: {e}")
        elif "already running" in str(e).lower():
            logger.warning("main: Event loop already running. This is unusual for a standalone script but might be okay in some contexts.")
        else:
            logger.critical(f"main: Unhandled RuntimeError in main: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"main: Unhandled critical error in main: {e}", exc_info=True)
    finally:
        logger.info("main: Main function finally block. Ensuring event loop is closed if running.")
        if loop.is_running():
            tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
            if tasks:
                logger.info(f"main: Cancelling {len(tasks)} outstanding tasks before closing loop...")
                for task in tasks:
                    task.cancel()
                try:
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    logger.info("main: Outstanding tasks cancelled/completed.")
                except Exception as e_gather:
                    logger.error(f"main: Error while gathering cancelled tasks: {e_gather}")

            logger.info("main: Closing asyncio event loop.")
            loop.close()
            logger.info("main: asyncio event loop closed.")
        else:
            logger.info("main: asyncio event loop was already closed.")


if __name__ == "__main__":
    logger.info(f"__main__: Script starting (Python version: {PTB_VER.split('.')[0]}.{PTB_VER.split('.')[1]}.x, Full PTB: {PTB_VER}).")
    main()
    logger.info("__main__: Script finished.")

# --- END OF FILE main.py ---