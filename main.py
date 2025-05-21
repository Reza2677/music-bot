# --- START OF FILE main.py ---
import asyncio
from telegram import Update, __version__ as TG_VER, Bot as TelegramBot
try:
    from telegram.ext import __version__ as PTB_VER
except ImportError:
    PTB_VER = TG_VER

from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          ContextTypes, ConversationHandler,
                          ApplicationBuilder, CallbackQueryHandler)
from aiohttp import web
import uvicorn
from starlette.applications import Starlette # <--- Import Starlette
from starlette.routing import Mount, Route # <--- Import برای روتینگ Starlette
from starlette.responses import PlainTextResponse # <--- برای health check ساده
from starlette.middleware import Middleware # <--- برای میان‌افزارها (اگر لازم شد)
from starlette.middleware.base import BaseHTTPMiddleware # <--- برای ساخت میان‌افزار سفارشی

# Import از config.py
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

bot_instance: 'MusicBot | None' = None

class MusicBot:
    # ... (کلاس MusicBot بدون تغییر باقی می‌ماند) ...
    # شامل __init__, _initialize_bot_dependencies, _setup_handlers,
    # _schedule_bot_jobs, shutdown_manual_worker, _handle_telegram_webhook,
    # startup_logic, shutdown_logic
    # (کد کلاس MusicBot را از نسخه قبلی که برایتان فرستادم کپی کنید)
    def __init__(self, token: str):
        self.token = token
        self.application: Application | None = None
        self.manual_request_queue: asyncio.Queue | None = None
        self.manual_request_worker_task: asyncio.Task | None = None
        logger.info(f"MusicBot instance CREATED. PTB Version: {PTB_VER}")

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
        if not self.application:
            logger.error("_setup_handlers: Application not initialized. Cannot add handlers.")
            return

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
        self.application.add_handler(main_conv_handler)
        logger.info("_setup_handlers: Main Conversation handler ADDED.")

        delete_history_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("delete_history", command_handlers.delete_history_prompt_command)],
            states={CONFIRM_DELETE_HISTORY: [CallbackQueryHandler(command_handlers.delete_history_confirmation_callback, pattern="^history_delete_confirm_")]},
            fallbacks=[CommandHandler("cancel", command_handlers.cancel_command)],
            name="delete_history_conversation", persistent=False, per_user=True, per_chat=True
        )
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
            logger.info("shutdown_manual_worker: Putting None to stop worker.")
            await self.manual_request_queue.put(None)

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
                except Exception as e_wait:
                    logger.error(f"shutdown_manual_worker: Error during worker task wait: {e_wait}")
            else:
                logger.info("shutdown_manual_worker: Worker task already done.")
        else:
            logger.info("shutdown_manual_worker: No worker task to shut down.")

    async def _handle_telegram_webhook(self, request: web.Request) -> web.Response: # این متد دیگر مستقیم توسط Starlette صدا زده نمی‌شود
        logger.debug(f"AIOHTTP Webhook received a request. Method: {request.method}")
        if request.method == "POST":
            try:
                update_json = await request.json()
                if self.application and self.application.bot:
                    update = Update.de_json(data=update_json, bot=self.application.bot)
                else:
                    logger.error("AIOHTTP Webhook: Application or application.bot is None. Cannot deserialize update.")
                    return web.Response(text="Internal Server Error: Bot not ready", status=500)

                if self.application:
                    await self.application.process_update(update)
                    logger.debug("AIOHTTP Webhook update processed via application.process_update().")
                    return web.Response(text="OK", status=200)
            except Exception as e:
                logger.error(f"AIOHTTP Error processing webhook update: {e}", exc_info=True)
                return web.Response(text="Error processing update", status=500)
        logger.warning(f"AIOHTTP Webhook received non-POST request: {request.method}")
        return web.Response(text="Only POST requests are allowed", status=405)


    async def startup_logic(self):
        logger.info("startup_logic: Attempting to start bot...")
        if not self.token or self.token == "YOUR_BOT_TOKEN_HERE":
            logger.critical("startup_logic: Bot TOKEN is not set. Aborting.")
            raise ValueError("Bot TOKEN is not set.")
        if not WEBHOOK_DOMAIN:
            logger.critical("startup_logic: WEBHOOK_DOMAIN is not set. Aborting webhook setup.")
            raise ValueError("WEBHOOK_DOMAIN is not set.")

        logger.info("startup_logic: Building application...")
        self.application = ApplicationBuilder().token(self.token).build()
        logger.info("startup_logic: Application BUILT.")
        logger.info("startup_logic: Initializing application (native initialize)...")
        await self.application.initialize()
        logger.info("startup_logic: Application NATIVELY INITIALIZED.")
        logger.info("startup_logic: Manually initializing bot dependencies...")
        await self._initialize_bot_dependencies()
        logger.info("startup_logic: Bot dependencies INITIALIZED.")
        logger.info("startup_logic: Setting up handlers...")
        self._setup_handlers()
        logger.info("startup_logic: Handlers SET UP.")

        # تنظیم وب‌هوک دیگر اینجا انجام نمی‌شود، بلکه در هندلر وب‌هوک Starlette انجام می‌شود
        # webhook_path = f"/{self.token}"
        # full_webhook_url = f"https://{WEBHOOK_DOMAIN}{webhook_path}"
        # ... کد تنظیم وب‌هوک حذف شد ...

        if self.application.job_queue:
            self._schedule_bot_jobs(self.application.job_queue)
        else:
            logger.error("startup_logic: JobQueue is not available. Jobs cannot be scheduled.")

        logger.info("startup_logic: Starting application (dispatcher)...")
        await self.application.start()
        logger.info("startup_logic: Application dispatcher STARTED.")
        # پیام موفقیت وب‌هوک هم جابجا می‌شود
        # logger.info(f"startup_logic: Bot is ALIVE and listening for webhook updates on {full_webhook_url}")

    async def shutdown_logic(self):
        logger.info("shutdown_logic: Initiating shutdown sequence...")
        await self.shutdown_manual_worker()
        if self.application and self.application.running:
            logger.info("shutdown_logic: Stopping PTB application dispatcher...")
            await self.application.stop()
        if self.application:
            logger.info("shutdown_logic: Shutting down PTB application...")
            await self.application.shutdown()
        # حذف وب‌هوک هم دیگر اینجا نیست
        logger.info("shutdown_logic: MusicBot application SHUT DOWN sequence complete.")


# --- Lifespan events for Starlette ---
async def starlette_startup():
    """Starlette startup event: initializes the bot."""
    global bot_instance
    logger.info("Starlette Lifespan: Startup initiated.")
    
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("Starlette Lifespan: Bot TOKEN is not set. Cannot start.")
        raise RuntimeError("Bot token is not configured properly for Starlette startup.")

    bot_instance = MusicBot(token=TOKEN)
    # bot_instance را در state اپلیکیشن Starlette ذخیره می‌کنیم
    # این کار در تابع create_starlette_app انجام می‌شود پس از ساخت bot_instance.

    try:
        await bot_instance.startup_logic() # PTB application را راه‌اندازی می‌کند
        
        # تنظیم وب‌هوک پس از راه‌اندازی PTB application
        if bot_instance.application and bot_instance.application.bot:
            webhook_path = f"/{TOKEN}" # مسیر وب‌هوک باید با مسیر در Starlette یکی باشد
            full_webhook_url = f"https://{WEBHOOK_DOMAIN}{webhook_path}"
            logger.info(f"Starlette Lifespan: Attempting to set webhook to: {full_webhook_url}")
            try:
                await bot_instance.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Starlette Lifespan: Attempted to delete any existing webhook.")
                await bot_instance.application.bot.set_webhook(url=full_webhook_url, allowed_updates=Update.ALL_TYPES)
                logger.info("Starlette Lifespan: >>>>>>> Webhook SET successfully! Bot should be operational. <<<<<<<")
            except Exception as e_webhook:
                logger.critical(f"Starlette Lifespan: FAILED to set webhook: {e_webhook}. Bot will likely not work.", exc_info=True)
                raise # این خطا باید باعث توقف راه‌اندازی شود
        else:
            logger.error("Starlette Lifespan: Bot application or bot object not available after startup_logic. Cannot set webhook.")
            raise RuntimeError("Bot application not ready for webhook setup.")

        logger.info("Starlette Lifespan: Bot startup logic COMPLETED and webhook set.")
    except Exception as e_startup:
        logger.critical(f"Starlette Lifespan: CRITICAL error during bot startup: {e_startup}", exc_info=True)
        raise RuntimeError(f"Failed to start bot during Starlette lifespan: {e_startup}") from e_startup

async def starlette_shutdown():
    """Starlette shutdown event: shuts down the bot."""
    global bot_instance
    logger.info("Starlette Lifespan: Shutdown initiated.")
    if bot_instance:
        # حذف وب‌هوک قبل از خاموش کردن کامل
        if bot_instance.application and bot_instance.application.bot and WEBHOOK_DOMAIN:
            try:
                logger.info("Starlette Lifespan: Final attempt to delete webhook...")
                await bot_instance.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Starlette Lifespan: Webhook DELETED (final attempt).")
            except Exception as e_wh_del_final:
                logger.error(f"Starlette Lifespan: Error deleting webhook during final shutdown: {e_wh_del_final}")
        
        await bot_instance.shutdown_logic()
    logger.info("Starlette Lifespan: Bot shutdown logic COMPLETED.")


# --- Starlette Webhook Handler ---
async def starlette_telegram_webhook(request): # دیگر از web.Request استفاده نمی‌کنیم بلکه از starlette.requests.Request
    """Handles incoming Telegram updates for Starlette."""
    global bot_instance
    if not bot_instance or not bot_instance.application or not bot_instance.application.bot:
        logger.error("Starlette Webhook: Bot instance or PTB application not available.")
        return PlainTextResponse("Bot not ready", status_code=503) # Service Unavailable

    if request.method == "POST":
        try:
            update_json = await request.json()
            update = Update.de_json(data=update_json, bot=bot_instance.application.bot)
            await bot_instance.application.process_update(update)
            logger.debug("Starlette Webhook update processed.")
            return PlainTextResponse("OK", status_code=200)
        except Exception as e:
            logger.error(f"Starlette Webhook: Error processing update: {e}", exc_info=True)
            return PlainTextResponse("Error processing update", status_code=500)
    
    logger.warning(f"Starlette Webhook received non-POST request: {request.method}")
    return PlainTextResponse("Only POST requests are allowed", status_code=405)

async def starlette_health_check(request):
    """Basic health check for Starlette."""
    logger.debug("Starlette Health check endpoint was pinged.")
    return PlainTextResponse("MusicBot (Starlette) is alive!", status_code=200)


# --- Factory function for Uvicorn ---
def create_starlette_app() -> Starlette:
    """Factory function to create the Starlette application."""
    global bot_instance # برای دسترسی در lifespan
    logger.info("create_starlette_app: Creating Starlette application...")

    if not TOKEN:
        logger.critical("create_starlette_app: TOKEN is not set. Cannot define webhook path.")
        raise ValueError("TOKEN is not set for Starlette app creation.")

    webhook_path = f"/{TOKEN}" # این مسیر باید با مسیر تنظیم وب‌هوک یکی باشد

    routes = [
        Route(webhook_path, endpoint=starlette_telegram_webhook, methods=["POST"]),
        Route("/", endpoint=starlette_health_check, methods=["GET"]),
    ]

    starlette_app = Starlette(
        routes=routes,
        on_startup=[starlette_startup], # لیست توابع startup
        on_shutdown=[starlette_shutdown] # لیست توابع shutdown
    )
    
    # اگر نیاز به ذخیره bot_instance در state اپلیکیشن Starlette دارید:
    # این کار بهتر است داخل starlette_startup انجام شود پس از اینکه bot_instance ساخته شد.
    # starlette_app.state.bot_instance = bot_instance 
    # و در هندلرها از request.app.state.bot_instance استفاده کنید.
    # اما با استفاده از متغیر global bot_instance، این کار فعلاً ضروری نیست.

    logger.info(f"create_starlette_app: Starlette application CREATED with webhook on '{webhook_path}' and health check on '/'.")
    return starlette_app


def main_for_uvicorn() -> None:
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("main_for_uvicorn: TOKEN is not available or is default. Exiting.")
        return
    if not WEBHOOK_DOMAIN:
        logger.critical("main_for_uvicorn: WEBHOOK_DOMAIN is not set. Exiting.")
        return

    logger.info("main_for_uvicorn: Starting Uvicorn server with Starlette app...")
    uvicorn.run(
        "main:create_starlette_app", # مسیر به تابع کارخانه‌ای Starlette
        host="0.0.0.0",
        port=PORT,
        factory=True,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    logger.info(f"__main__: Script starting (PTB Version: {PTB_VER}). Running main_for_uvicorn.")
    try:
        main_for_uvicorn()
    except Exception as e_main_uvicorn:
        logger.critical(f"__main__: Critical error running main_for_uvicorn: {e_main_uvicorn}", exc_info=True)
    finally:
        logger.info("__main__: Script finished executing main_for_uvicorn().")

# --- END OF FILE main.py ---