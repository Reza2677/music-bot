from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler,
    ApplicationBuilder, CallbackQueryHandler
)
import asyncio

from music_bot.config import (
    TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM,
    CONFIRM_SINGER_SUGGESTION, CONFIRM_DELETE_HISTORY, APP_ENV
)

from music_bot.database.user_db import DatabaseHandler
from music_bot.database.track_db import TrackDatabaseHandler

from music_bot.services.user_manager import UserManager
from music_bot.services.music_fetcher import MusicFetcher
from music_bot.services.track_searcher import TrackSearcher

from music_bot.handlers import command_handlers
from music_bot.handlers import menu_handlers
from music_bot.handlers import job_handlers


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
        self.manual_request_worker_task = None
        logger.info(f"MusicBot instance CREATED. APP_ENV: {APP_ENV}")

    async def _initialize_bot_dependencies(self):
        """
        راه‌اندازی و پیکربندی وابستگی‌های ربات، پایگاه داده‌ها و سرویس‌های مورد نیاز
        """
        logger.info(">>>>>>>> _initialize_bot_dependencies: ENTERED <<<<<<<<")
        if not self.application:
            logger.critical("_initialize_bot_dependencies: Application is not initialized. Cannot proceed.")
            return
        
        try:
            # مقداردهی اولیه پایگاه‌های داده
            logger.info("_initialize_bot_dependencies: Initializing database handlers...")
            user_db = DatabaseHandler(DB_NAME)
            track_db = TrackDatabaseHandler(TRACK_DB_NAME)
            self.application.bot_data['user_db_handler'] = user_db
            self.application.bot_data['track_db_handler'] = track_db
            logger.info("_initialize_bot_dependencies: Database handlers ADDED to bot_data.")
            
            # واکشی و ذخیره‌سازی نام‌های تمام خوانندگان
            logger.info("_initialize_bot_dependencies: Fetching and caching all singer names...")
            all_singer_names_set = await track_db.get_all_unique_singer_names()
            self.application.bot_data['all_singer_names_list'] = list(all_singer_names_set)
            logger.info(f"_initialize_bot_dependencies: Stored {len(all_singer_names_set)} unique singer names in bot_data.")
            
            # مقداردهی سرویس‌های اصلی
            logger.info("_initialize_bot_dependencies: Initializing services...")
            user_manager = UserManager(user_db)
            music_fetcher = MusicFetcher()
            track_searcher = TrackSearcher(track_db)
            self.application.bot_data['user_manager'] = user_manager
            self.application.bot_data['music_fetcher'] = music_fetcher
            self.application.bot_data['track_searcher'] = track_searcher
            logger.info("_initialize_bot_dependencies: Core services ADDED to bot_data.")
            
            # راه‌اندازی صف درخواست‌های دستی و کارگر مربوطه
            logger.info("_initialize_bot_dependencies: Initializing manual request queue and worker...")
            self.manual_request_queue = asyncio.Queue()
            self.application.bot_data['manual_request_queue'] = self.manual_request_queue
            self.manual_request_worker_task = asyncio.create_task(
                menu_handlers.manual_request_worker(self.application)
            )
            logger.info("_initialize_bot_dependencies: Manual request queue and worker task STARTED.")
            
            # زمانبندی کارهای دوره‌ای ربات
            logger.info("_initialize_bot_dependencies: Scheduling bot jobs...")
            self._schedule_bot_jobs(self.application.job_queue)
            logger.info("_initialize_bot_dependencies: Bot jobs SCHEDULED.")
            
        except Exception as e_deps:
            logger.critical(f">>>>>>>> _initialize_bot_dependencies: EXCEPTION occurred: {e_deps} <<<<<<<<", exc_info=True)
            raise 
        
        logger.info(">>>>>>>> _initialize_bot_dependencies: EXITED SUCCESSFULLY <<<<<<<<")

    def _setup_handlers(self):
        """
        تنظیم و پیکربندی تمام هندلرهای مورد نیاز برای مدیریت دستورات و گفتگوها
        """
        logger.info("_setup_handlers: Configuring all handlers...")

        # تعریف گفتگوی اصلی منوها
        main_conv_handler = ConversationHandler(
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
            name="main_menu_conversation",
            persistent=False
        )
        
        if self.application:
            self.application.add_handler(main_conv_handler)
            logger.info("_setup_handlers: Main Conversation handler ADDED.")
        else:
            logger.error("_setup_handlers: Application not initialized for Main Conversation handler.")

        # گفتگوی جداگانه برای حذف تاریخچه
        delete_history_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("delete_history", command_handlers.delete_history_prompt_command)],
            states={
                CONFIRM_DELETE_HISTORY: [
                    CallbackQueryHandler(command_handlers.delete_history_confirmation_callback, pattern="^history_delete_confirm_")
                ]
            },
            fallbacks=[
                CommandHandler("cancel", command_handlers.cancel_command)
            ],
            name="delete_history_conversation",
            persistent=False,
            per_user=True,  # حفظ user_data جداگانه برای هر کاربر
            per_chat=True   # حفظ chat_data جداگانه برای هر گفتگو
        )
        
        if self.application:
            self.application.add_handler(delete_history_conv_handler)
            logger.info("_setup_handlers: Delete Sent Music History Conversation handler ADDED.")
        else:
            logger.error("_setup_handlers: Application not initialized for Delete History Conversation handler.")

    def _schedule_bot_jobs(self, job_queue):
        """
        زمانبندی کارهای دوره‌ای ربات
        
        Args:
            job_queue: صف کارهای برنامه
        """
        logger.info("_schedule_bot_jobs: Scheduling...")
        if job_queue:
            job_queue.run_repeating(job_handlers.run_music_processing_job, interval=86000, first=0, name="MusicDataProcessingJob")
            logger.info("_schedule_bot_jobs: Music data processing job SCHEDULED.")
            job_queue.run_repeating(job_handlers.run_user_notification_job, interval=86900, first=0, name="DailyUserNotificationJob")
            logger.info("_schedule_bot_jobs: Daily user notification job SCHEDULED.")
        else:
            logger.error("_schedule_bot_jobs: JobQueue not available.")
            
    async def shutdown_manual_worker(self):
        """
        خاموش کردن و پاکسازی کارگر درخواست‌های دستی
        """
        logger.info("shutdown_manual_worker: Attempting to shutdown manual worker...")
        if self.manual_request_queue and self.manual_request_worker_task and not self.manual_request_worker_task.done():
            if self.manual_request_queue.empty():
                logger.info("shutdown_manual_worker: Queue is empty, putting None to stop worker.")
                await self.manual_request_queue.put(None)
            else:
                logger.warning("shutdown_manual_worker: Manual request queue is not empty. Worker will process items then stop if None is next.")
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
                    try:
                        await self.manual_request_worker_task
                    except asyncio.CancelledError:
                        logger.info("shutdown_manual_worker: Worker task cancellation confirmed.")
                    except Exception as e_cancel:
                        logger.error(f"shutdown_manual_worker: Error during worker task cancellation: {e_cancel}")
                except Exception as e_wait:
                    logger.error(f"shutdown_manual_worker: Error during worker task wait: {e_wait}")
        else:
            logger.info("shutdown_manual_worker: No worker task to shut down.")

    async def run(self):
        """
        آغاز عملیات اصلی ربات و پیکربندی تمامی موارد لازم
        """
        logger.info(f"run: Attempting to start bot with token: {'***' + self.token[-6:] if self.token else 'Not Set'}")
        try:
            # ساخت و راه‌اندازی برنامه
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
            
            logger.info("run: Starting application (dispatcher, job_queue)...")
            await self.application.start() 
            logger.info("run: Application STARTED.")
            
            logger.info("run: Starting updater (polling)...")
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("run: Bot IS POLLING...")
            
            # حلقه اصلی اجرا
            while self.application.updater.running:
                await asyncio.sleep(1)
                
        except (KeyboardInterrupt, SystemExit):
            logger.info("run: Bot shutdown signal received.")
        except Exception as e:
            logger.critical(f"run: Unhandled exception: {e}", exc_info=True)
        finally:
            logger.info("run: Initiating FINALLY block for shutdown...")
            if self.application and hasattr(self.application, 'updater') and self.application.updater.running:
                logger.info("run: Stopping updater...")
                await self.application.updater.stop()
                
            await self.shutdown_manual_worker()
            
            if self.application:
                logger.info("run: Shutting down application...")
                await self.application.shutdown()
                
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