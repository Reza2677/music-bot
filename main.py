from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler,
    ApplicationBuilder, CallbackQueryHandler # CallbackQueryHandler اضافه شد
)
import asyncio

from music_bot.config import (
    TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM,
    CONFIRM_SINGER_SUGGESTION, # وضعیت جدید اضافه شد
    APP_ENV
)

from music_bot.database.user_db import DatabaseHandler
from music_bot.database.track_db import TrackDatabaseHandler

from music_bot.services.user_manager import UserManager
from music_bot.services.music_fetcher import MusicFetcher
from music_bot.services.track_searcher import TrackSearcher

from music_bot.handlers import command_handlers
from music_bot.handlers import menu_handlers # شامل singer_suggestion_callback_handler هم می‌شود
from music_bot.handlers import job_handlers


class MusicBot:
    def __init__(self, token: str):
        self.token = token
        self.application: Application = None
        self.manual_request_queue: asyncio.Queue = None
        self.manual_request_worker_task: asyncio.Task = None
        logger.info(f"MusicBot instance CREATED. APP_ENV: {APP_ENV}")

    async def _initialize_bot_dependencies(self):
        logger.info(">>>>>>>> _initialize_bot_dependencies: ENTERED <<<<<<<<")
        if not self.application:
            logger.critical("_initialize_bot_dependencies: Application is not initialized. Cannot proceed.")
            return

        try:
            logger.info("_initialize_bot_dependencies: Initializing database handlers...")
            user_db = DatabaseHandler(DB_NAME)
            track_db = TrackDatabaseHandler(TRACK_DB_NAME)
            logger.info(f"_initialize_bot_dependencies: user_db type: {type(user_db)}, track_db type: {type(track_db)}")

            self.application.bot_data['user_db_handler'] = user_db
            self.application.bot_data['track_db_handler'] = track_db
            logger.info("_initialize_bot_dependencies: Database handlers ADDED to bot_data.")

            # --- کش کردن لیست خوانندگان ---
            logger.info("_initialize_bot_dependencies: Fetching and caching all singer names...")
            all_singer_names_set = await track_db.get_all_unique_singer_names()
            self.application.bot_data['all_singer_names_list'] = list(all_singer_names_set)
            logger.info(f"_initialize_bot_dependencies: Stored {len(all_singer_names_set)} unique singer names in bot_data.")
            # -----------------------------

            logger.info("_initialize_bot_dependencies: Initializing services...")
            user_manager = UserManager(user_db)
            logger.info(f"_initialize_bot_dependencies: user_manager type: {type(user_manager)}")
            music_fetcher = MusicFetcher()
            logger.info(f"_initialize_bot_dependencies: music_fetcher type: {type(music_fetcher)}")
            track_searcher = TrackSearcher(track_db)
            logger.info(f"_initialize_bot_dependencies: track_searcher type: {type(track_searcher)}")

            self.application.bot_data['user_manager'] = user_manager
            logger.info(f">>>>>>>> _initialize_bot_dependencies: user_manager ADDED. Bot_data keys: {list(self.application.bot_data.keys())} <<<<<<<<")
            
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

            logger.info("_initialize_bot_dependencies: Scheduling bot jobs...")
            self._schedule_bot_jobs(self.application.job_queue)
            logger.info("_initialize_bot_dependencies: Bot jobs SCHEDULED.")

        except Exception as e_deps:
            logger.critical(f">>>>>>>> _initialize_bot_dependencies: EXCEPTION occurred: {e_deps} <<<<<<<<", exc_info=True)
            raise 
        
        logger.info(">>>>>>>> _initialize_bot_dependencies: EXITED SUCCESSFULLY <<<<<<<<")

    def _setup_conversation_handler(self):
        logger.info("_setup_conversation_handler: Configuring...")
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", command_handlers.start_command)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['list']}$"), menu_handlers.list_menu_prompt_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['receive_music_now']}$"), menu_handlers.receive_music_now_handler),
                ],
                LIST_MENU: [
                    MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['edit_list']}|{KEYBOARD_TEXTS['remove_list']}|{KEYBOARD_TEXTS['back']})$"), menu_handlers.list_menu_router),
                ],
                EDIT_LIST_MENU: [
                    MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['add']}|{KEYBOARD_TEXTS['delete']}|{KEYBOARD_TEXTS['back']})$"), menu_handlers.edit_list_menu_router),
                ],
                ADD_SINGER: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['delete']}$"), menu_handlers.ignore_delete_in_add_handler), # این شاید دیگر لازم نباشد
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['delete']})$"), menu_handlers.save_singer_handler),
                ],
                DELETE_SINGER: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_edit_list_menu_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['add']}$"), menu_handlers.ignore_add_in_delete_handler), # این شاید دیگر لازم نباشد
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['add']})$"), menu_handlers.remove_singer_handler),
                ],
                REMOVE_LIST_CONFIRM: [
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['confirm']}$"), menu_handlers.confirm_remove_list_handler),
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['cancel_action']}$"), menu_handlers.cancel_remove_list_handler),
                ],
                CONFIRM_SINGER_SUGGESTION: [
                    CallbackQueryHandler(menu_handlers.singer_suggestion_callback_handler, pattern="^suggest_"), # پترن می‌تواند suggest_idx_ یا suggest_none را بگیرد
                    MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), menu_handlers.back_to_add_singer_from_suggestion),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handlers.fallback_text_in_suggestion_state)
                ],
            },
            fallbacks=[CommandHandler("cancel", command_handlers.cancel_command)],
        )
        if self.application:
            self.application.add_handler(conv_handler)
            logger.info("_setup_conversation_handler: Conversation handler ADDED to application.")
        else:
            logger.error("_setup_conversation_handler: Application not initialized when trying to add conversation handler.")

    def _schedule_bot_jobs(self, job_queue):
        logger.info("_schedule_bot_jobs: Scheduling...")
        if job_queue:
            # جاب اصلی روزانه که شامل پردازش موسیقی و سپس نوتیفیکیشن است
            # (اگر از این مدل استفاده می‌کنید، مطمئن شوید job_handlers.run_daily_main_job تعریف شده)
            # یا دو جاب جداگانه:
            job_queue.run_repeating(job_handlers.run_music_processing_job, interval=86000, first=10, name="MusicDataProcessingJob") # تغییر نام برای وضوح
            logger.info("_schedule_bot_jobs: Music data processing job SCHEDULED.")
            job_queue.run_repeating(job_handlers.run_user_notification_job, interval=86400, first=60, name="DailyUserNotificationJob") # با کمی تاخیر نسبت به جاب اول
            logger.info("_schedule_bot_jobs: Daily user notification job SCHEDULED.")
        else:
            logger.error("_schedule_bot_jobs: JobQueue not available.")

    async def shutdown_manual_worker(self):
        logger.info("shutdown_manual_worker: Attempting to shutdown manual worker...")
        if self.manual_request_queue and self.manual_request_worker_task and not self.manual_request_worker_task.done():
            # فقط اگر صف خالی است None بفرست، در غیر اینصورت اجازه بده کارگر آیتم‌های باقیمانده را پردازش کند
            # و بعدا خودش با None خارج شود یا با cancel متوقف شود.
            # این بخش نیاز به بازبینی دارد تا مطمئن شویم کارگر آیتم‌ها را از دست نمی‌دهد.
            # راه ساده‌تر: همیشه None بفرست و در کارگر پس از پردازش آیتم فعلی، اگر None بود خارج شو.
            if self.manual_request_queue.empty():
                 logger.info("shutdown_manual_worker: Queue is empty, putting None to stop worker.")
                 await self.manual_request_queue.put(None)
            else:
                 logger.warning("shutdown_manual_worker: Manual request queue is not empty. Worker will process items then stop if None is next.")
                 # برای اطمینان از خروج، یک None دیگر هم ممکن است لازم باشد اگر آیتم‌های زیادی در صف است،
                 # یا اینکه فقط به cancel تکیه کنیم.
                 # فعلا یک None می‌فرستیم، کارگر باید پس از پردازش آیتم فعلی، این None را بگیرد و خارج شود.
                 await self.manual_request_queue.put(None)


        if self.manual_request_worker_task:
            if self.manual_request_worker_task.done():
                logger.info("shutdown_manual_worker: Worker task already done.")
            else:
                logger.info("shutdown_manual_worker: Waiting for worker task to finish (max 10s)...")
                try:
                    await asyncio.wait_for(self.manual_request_worker_task, timeout=10.0)
                    logger.info("shutdown_manual_worker: Worker task finished gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("shutdown_manual_worker: Worker task did not shut down gracefully in time. Cancelling.")
                    self.manual_request_worker_task.cancel()
                    try: await self.manual_request_worker_task
                    except asyncio.CancelledError: logger.info("shutdown_manual_worker: Worker task cancellation confirmed.")
                    except Exception as e_cancel: logger.error(f"shutdown_manual_worker: Error during worker task cancellation: {e_cancel}")
                except Exception as e_wait:
                    logger.error(f"shutdown_manual_worker: Error during worker task wait: {e_wait}")
        else:
            logger.info("shutdown_manual_worker: No worker task to shut down.")

    async def run(self):
        logger.info(f"run: Attempting to start bot with token: {'***' + self.token[-6:] if self.token else 'Not Set'}")
        try:
            logger.info("run: Building application...")
            self.application = (
                ApplicationBuilder()
                .token(self.token)
                .build()
            )
            logger.info("run: Application BUILT.")

            logger.info("run: Initializing application (native initialize)...")
            await self.application.initialize() 
            logger.info("run: Application NATIVELY INITIALIZED.")
            
            logger.info("run: Manually initializing bot dependencies...")
            await self._initialize_bot_dependencies() 
            logger.info("run: Bot dependencies INITIALIZED.")

            logger.info(f"run: bot_data keys AFTER manual dependencies init: {list(self.application.bot_data.keys())}")
            
            logger.info("run: Setting up conversation handler...")
            self._setup_conversation_handler()
            logger.info("run: Conversation handler SET UP.")

            logger.info("run: Starting application (dispatcher, job_queue)...")
            await self.application.start() 
            logger.info("run: Application STARTED.")

            logger.info("run: Starting updater (polling)...")
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("run: Bot IS POLLING...")
            
            while self.application.updater.running:
                await asyncio.sleep(1)

        except (KeyboardInterrupt, SystemExit):
            logger.info("run: Bot shutdown signal received (KeyboardInterrupt/SystemExit).")
        except Exception as e:
            logger.critical(f"run: An unhandled exception occurred at the bot's top level: {e}", exc_info=True)
        finally:
            logger.info("run: Initiating FINALLY block for shutdown...")
            if self.application and hasattr(self.application, 'updater') and self.application.updater.running:
                logger.info("run: Stopping updater...")
                await self.application.updater.stop()
            
            # توقف کارگر دستی قبل از shutdown کامل اپلیکیشن
            await self.shutdown_manual_worker()

            if self.application:
                logger.info("run: Shutting down application (includes stopping jobs)...")
                await self.application.shutdown()
            
            logger.info("run: MusicBot application SHUT DOWN.")


def main() -> None:
    if not TOKEN:
        logger.critical("main: TELEGRAM_BOT_TOKEN is not set. Bot cannot start.")
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
            logger.critical(f"main: RuntimeError during asyncio.run: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.critical(f"main: Critical error during asyncio.run: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("__main__: Script starting.")
    main()
    logger.info("__main__: Script finished.")