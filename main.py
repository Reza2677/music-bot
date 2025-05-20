from telegram import Update
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          ContextTypes, ConversationHandler,
                          ApplicationBuilder, CallbackQueryHandler)
import asyncio
from aiohttp import web
from config import (TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
                    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER,
                    DELETE_SINGER, REMOVE_LIST_CONFIRM,
                    CONFIRM_SINGER_SUGGESTION, CONFIRM_DELETE_HISTORY, APP_ENV,
                    PORT, WEBHOOK_DOMAIN)
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
    """
    ربات اصلی موسیقی که مدیریت عملکرد و چرخه زندگی ربات را به عهده دارد.
    """

    def __init__(self, token: str):
        """
        مقداردهی اولیه ربات

        Args:
            token: توکن API تلگرام
        """
        self.token = token
        self.application = None
        self.manual_request_queue = None
        self.aiohttp_runner = None  # برای نگهداری رانر وب سرور
        self.manual_request_worker_task = None
        logger.info(f"MusicBot instance CREATED. APP_ENV: {APP_ENV}")

    async def _initialize_bot_dependencies(self):
        """
        راه‌اندازی و پیکربندی وابستگی‌های ربات، پایگاه داده‌ها و سرویس‌های مورد نیاز
        """
        logger.info(">>>>>>>> _initialize_bot_dependencies: ENTERED <<<<<<<<")
        if not self.application:
            logger.critical(
                "_initialize_bot_dependencies: Application is not initialized. Cannot proceed."
            )
            return

        try:
            # مقداردهی اولیه پایگاه‌های داده
            logger.info(
                "_initialize_bot_dependencies: Initializing database handlers..."
            )
            user_db = DatabaseHandler(DB_NAME)
            track_db = TrackDatabaseHandler(TRACK_DB_NAME)
            self.application.bot_data['user_db_handler'] = user_db
            self.application.bot_data['track_db_handler'] = track_db
            logger.info(
                "_initialize_bot_dependencies: Database handlers ADDED to bot_data."
            )

            # واکشی و ذخیره‌سازی نام‌های تمام خوانندگان
            logger.info(
                "_initialize_bot_dependencies: Fetching and caching all singer names..."
            )
            all_singer_names_set = await track_db.get_all_unique_singer_names()
            self.application.bot_data['all_singer_names_list'] = list(
                all_singer_names_set)
            logger.info(
                f"_initialize_bot_dependencies: Stored {len(all_singer_names_set)} unique singer names in bot_data."
            )

            # مقداردهی سرویس‌های اصلی
            logger.info(
                "_initialize_bot_dependencies: Initializing services...")
            user_manager = UserManager(user_db)
            music_fetcher = MusicFetcher()
            track_searcher = TrackSearcher(track_db)
            self.application.bot_data['user_manager'] = user_manager
            self.application.bot_data['music_fetcher'] = music_fetcher
            self.application.bot_data['track_searcher'] = track_searcher
            logger.info(
                "_initialize_bot_dependencies: Core services ADDED to bot_data."
            )

            # راه‌اندازی صف درخواست‌های دستی و کارگر مربوطه
            logger.info(
                "_initialize_bot_dependencies: Initializing manual request queue and worker..."
            )
            self.manual_request_queue = asyncio.Queue()
            self.application.bot_data[
                'manual_request_queue'] = self.manual_request_queue
            self.manual_request_worker_task = asyncio.create_task(
                menu_handlers.manual_request_worker(self.application))
            logger.info(
                "_initialize_bot_dependencies: Manual request queue and worker task STARTED."
            )

            # زمانبندی کارهای دوره‌ای ربات
            logger.info("_initialize_bot_dependencies: Scheduling bot jobs...")
            self._schedule_bot_jobs(self.application.job_queue)
            logger.info("_initialize_bot_dependencies: Bot jobs SCHEDULED.")

        except Exception as e_deps:
            logger.critical(
                f">>>>>>>> _initialize_bot_dependencies: EXCEPTION occurred: {e_deps} <<<<<<<<",
                exc_info=True)
            raise

        logger.info(
            ">>>>>>>> _initialize_bot_dependencies: EXITED SUCCESSFULLY <<<<<<<<"
        )

    def _setup_handlers(self):
        """
        تنظیم و پیکربندی تمام هندلرهای مورد نیاز برای مدیریت دستورات و گفتگوها
        """
        logger.info("_setup_handlers: Configuring all handlers...")

        # تعریف گفتگوی اصلی منوها
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

        # گفتگوی جداگانه برای حذف تاریخچه
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
            per_user=True,  # حفظ user_data جداگانه برای هر کاربر
            per_chat=True  # حفظ chat_data جداگانه برای هر گفتگو
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
        """
        زمانبندی کارهای دوره‌ای ربات

        Args:
            job_queue: صف کارهای برنامه
        """
        logger.info("_schedule_bot_jobs: Scheduling...")
        if job_queue:
            job_queue.run_repeating(job_handlers.run_music_processing_job,
                                    interval=86000,
                                    first=0,
                                    name="MusicDataProcessingJob")
            logger.info(
                "_schedule_bot_jobs: Music data processing job SCHEDULED.")
            job_queue.run_repeating(job_handlers.run_user_notification_job,
                                    interval=86900,
                                    first=0,
                                    name="DailyUserNotificationJob")
            logger.info(
                "_schedule_bot_jobs: Daily user notification job SCHEDULED.")
        else:
            logger.error("_schedule_bot_jobs: JobQueue not available.")

    async def shutdown_manual_worker(self):
        """
        خاموش کردن و پاکسازی کارگر درخواست‌های دستی
        """
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

    async def _handle_telegram_webhook(self,
                                       request: web.Request) -> web.Response:
        """هندلر برای دریافت آپدیت‌ها از تلگرام."""
        logger.debug(f"Webhook received a request. Method: {request.method}")
        if request.method == "POST":
            try:
                update_json = await request.json()
                # روش اول (ساده‌تر برای de_json):
                update = Update.de_json(update_json)
                # یا اگر می‌خواهید bot را پاس بدهید (که معتبر است اما شاید لازم نباشد):
                # update = Update.de_json(update_json, self.application.bot)

                # استفاده از process_update به جای دسترسی مستقیم به صف
                if self.application:
                    await self.application.process_update(update)
                    logger.debug(
                        "Webhook update processed via application.process_update()."
                    )  # لاگ به‌روز شده
                    return web.Response(text="OK", status=200)
                else:
                    logger.error(
                        "Application object is None. Cannot process update.")
                    return web.Response(text="Application not initialized",
                                        status=500)
            except Exception as e:
                logger.error(f"Error processing webhook update: {e}",
                             exc_info=True)
                return web.Response(text="Error processing update", status=500)
        logger.warning(f"Webhook received non-POST request: {request.method}")
        return web.Response(text="Only POST requests are allowed", status=405)

    async def _health_check(self, request: web.Request) -> web.Response:
        """اندپوینت برای UptimeRobot یا سایر سرویس‌های پینگ."""
        logger.debug("Health check endpoint was pinged.")
        return web.Response(text=f"MusicBot is alive! APP_ENV: {APP_ENV}",
                            status=200)

    async def run(self):
        """
        آغاز عملیات اصلی ربات و پیکربندی تمامی موارد لازم با استفاده از وب‌هوک.
        """
        logger.info(
            f"run: Attempting to start bot with token: {'***' + self.token[-6:] if self.token else 'Not Set'}"
        )

        if not self.token:
            logger.critical("run: Bot TOKEN is not set. Aborting.")
            return

        if APP_ENV == "production" and not WEBHOOK_DOMAIN:
            logger.critical(
                "run: WEBHOOK_DOMAIN is not set in production. Replit env vars (REPL_SLUG, REPL_OWNER) might be missing. Aborting webhook setup."
            )
            # می‌توانید در اینجا به حالت polling برگردید یا خطا ایجاد کنید
            # For now, we abort if webhook domain is needed but not available.
            return

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
            logger.info(
                f"run: bot_data keys AFTER manual dependencies init: {list(self.application.bot_data.keys())}"
            )

            logger.info("run: Setting up handlers...")
            self._setup_handlers()
            logger.info("run: Handlers SET UP.")

            # --- بخش مربوط به وب‌هوک و وب سرور ---
            webhook_path = f"/{self.token}"  # مسیر وب‌هوک (محرمانه)

            # راه‌اندازی وب سرور aiohttp
            web_server = web.Application()
            web_server.router.add_post(webhook_path,
                                       self._handle_telegram_webhook)
            web_server.router.add_get("/",
                                      self._health_check)  # برای UptimeRobot

            self.aiohttp_runner = web.AppRunner(web_server)
            await self.aiohttp_runner.setup()
            site = web.TCPSite(self.aiohttp_runner, host="0.0.0.0", port=PORT)
            await site.start()
            logger.info(
                f"Web server started on 0.0.0.0:{PORT}. Health check on '/', Webhook on '{webhook_path}'"
            )

            if WEBHOOK_DOMAIN:
                full_webhook_url = f"https://{WEBHOOK_DOMAIN}{webhook_path}"
                logger.info(
                    f"run: Attempting to set webhook to{full_webhook_url}"
                )  # لاگ برای اطمینان
                try:
                    await self.application.bot.set_webhook(
                        url=full_webhook_url,
                        allowed_updates=Update.ALL_TYPES,
                        # drop_pending_updates=True # اختیاری
                    )
                    logger.info("run: Webhook SET successfully.")
                except telegram.error.BadRequest as e_bad_request:  # گرفتن خطای خاص BadRequest
                    logger.error(
                        f"run: FAILED to set webhook: {e_bad_request}. Continuing without webhook for testing purposes."
                    )
                    logger.error(
                        "run: The bot will NOT receive updates from Telegram, but the web server remains active for browser testing."
                    )
                except Exception as e_webhook:  # گرفتن سایر خطاهای احتمالی در set_webhook
                    logger.error(
                        f"run: An unexpected error occurred while setting webhook: {e_webhook}. Continuing without webhook."
                    )
            else:
                logger.warning(
                    "run: WEBHOOK_DOMAIN not set. Skipping webhook setup.")

                # JobQueue Scheduling (مطمئن شوید اینجاست)
            if self.application.job_queue:
                self._schedule_bot_jobs(self.application.job_queue)
                logger.info(
                    "run: Bot jobs SCHEDULED (after application init and before start)."
                )
            else:
                logger.error(
                    "run: JobQueue is still not available after application.initialize(). Jobs cannot be scheduled."
                )

            logger.info("run: Starting application (dispatcher)...")
            await self.application.start()
            logger.info("run: Application dispatcher STARTED.")

            logger.info(
                "run: Bot is ALIVE and listening. Web server active for browser tests."
            )
            logger.info(
                f"!!! If webhook failed, test this URL in your browser: https://{WEBHOOK_DOMAIN}/"
            )  # یادآوری مهم

            # حلقه اصلی برای زنده نگه داشتن برنامه
            stop_event = asyncio.Event()
            try:
                await stop_event.wait()
            except (KeyboardInterrupt, SystemExit):
                logger.info(
                    "run: Bot shutdown signal received (KeyboardInterrupt/SystemExit)."
                )

        except (KeyboardInterrupt,
                SystemExit) as sig:  # گرفتن سیگنال در اینجا هم مهم است
            logger.info(
                f"run: Bot shutdown signal received ({type(sig).__name__}).")
        except Exception as e:
            logger.critical(f"run: Unhandled exception during run: {e}",
                            exc_info=True)
        finally:
            logger.info("run: Initiating FINALLY block for shutdown...")

            # ۱. توقف وب سرور aiohttp
            if self.aiohttp_runner:
                logger.info("run: Cleaning up aiohttp web server...")
                await self.aiohttp_runner.cleanup()
                logger.info("run: aiohttp web server CLEANED UP.")

            # ۲. حذف وب‌هوک (اختیاری اما توصیه شده)
            if self.application and self.application.bot and WEBHOOK_DOMAIN:
                try:
                    logger.info("run: Deleting webhook...")
                    await self.application.bot.delete_webhook()
                    logger.info("run: Webhook DELETED.")
                except Exception as e_wh_del:
                    logger.error(f"run: Error deleting webhook: {e_wh_del}")

            # ۳. خاموش کردن کارگر دستی
            await self.shutdown_manual_worker()

            # ۴. خاموش کردن اپلیکیشن PTB
            if self.application:
                logger.info("run: Stopping PTB application dispatcher...")
                await self.application.stop()  # توقف دیسپچر
                logger.info("run: Shutting down PTB application...")
                await self.application.shutdown()  # پاکسازی منابع اپلیکیشن

            logger.info("run: MusicBot application SHUT DOWN.")


def main() -> None:
    """
    تابع اصلی برنامه که نقطه شروع اجرا است
    """
    if not TOKEN:
        logger.critical("main: TOKEN is not set.")
        return

    logger.info("main: Creating MusicBot instance...")
    bot_instance = MusicBot(token=TOKEN)

    try:
        logger.info("main: Running bot_instance.run()...")
        asyncio.run(bot_instance.run())
    except RuntimeError as e:
        if "already running" in str(e).lower():
            logger.warning("main: Event loop already running.")
        else:
            logger.critical(f"main: RuntimeError: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.critical(f"main: Critical error: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("__main__: Script starting.")
    main()
    logger.info("__main__: Script finished.")
