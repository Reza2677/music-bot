from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler,
    ApplicationBuilder, Defaults
)
import asyncio

# Configuration - استفاده از وارد کردن نسبی صریح
from .config import (  # <--- تغییر: اضافه شدن نقطه
    TOKEN, DB_NAME, TRACK_DB_NAME, logger, KEYBOARD_TEXTS,
    MAIN_MENU, LIST_MENU, EDIT_LIST_MENU, ADD_SINGER, DELETE_SINGER, REMOVE_LIST_CONFIRM, SET_TIME
)

# Database - استفاده از وارد کردن نسبی صریح
from .database import DatabaseHandler, TrackDatabaseHandler  # <--- تغییر: اضافه شدن نقطه

# Services - استفاده از وارد کردن نسبی صریح
from .services import UserManager, MusicFetcher, TrackSearcher  # <--- تغییر: اضافه شدن نقطه

# Handlers - استفاده از وارد کردن نسبی صریح
from .handlers import (  # <--- تغییر: اضافه شدن نقطه
    start_command, cancel_command,
    main_menu_router, list_menu_router, edit_list_menu_router,
    add_singer_prompt_handler, save_singer_handler,
    delete_singer_prompt_handler, remove_singer_handler,
    remove_list_prompt_handler, confirm_remove_list_handler, cancel_remove_list_handler,
    set_time_prompt_handler, save_time_handler,
    back_to_main_menu_handler, back_to_list_menu_handler, back_to_edit_list_menu_handler,
    ignore_delete_in_add_handler, ignore_add_in_delete_handler,
    run_music_processing_job, run_user_notification_job,
    # اگر show_user_singers_list مستقیما اینجا استفاده نمی‌شود، نیازی به وارد کردنش نیست
    # اگر استفاده می‌شود:
    # show_user_singers_list
)

async def post_init_actions(application: Application):
    logger.info("Performing post-initialization actions...")
    
    # Initialize database handlers
    # این بخش به همین صورت باقی می‌ماند چون DatabaseHandler و TrackDatabaseHandler از .database وارد شده‌اند
    user_db = DatabaseHandler(DB_NAME)
    track_db = TrackDatabaseHandler(TRACK_DB_NAME)
    application.bot_data['user_db_handler'] = user_db
    application.bot_data['track_db_handler'] = track_db
    logger.info("Database handlers initialized.")

    # Initialize services
    # این بخش هم به همین صورت باقی می‌ماند
    user_manager = UserManager(user_db)
    music_fetcher = MusicFetcher() 
    track_searcher = TrackSearcher(track_db)
    
    application.bot_data['user_manager'] = user_manager
    application.bot_data['music_fetcher'] = music_fetcher
    application.bot_data['track_searcher'] = track_searcher
    logger.info("Core services initialized and stored in bot_data.")

    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(run_music_processing_job, interval=14400, first=10, name="MusicFetchJob") 
        logger.info("Music fetching job scheduled.")
        job_queue.run_repeating(run_user_notification_job, interval=120, first=0, name="UserNotificationJob")
        logger.info("User notification job scheduled.")
    else:
        logger.error("JobQueue not available. Scheduled tasks will not run.")
    
    logger.info("Post-initialization complete.")


def main() -> None:
    logger.info("Starting bot...")
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init_actions)
        .build()
    )
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['list']}|{KEYBOARD_TEXTS['set_time']})$"), main_menu_router),
            ],
            LIST_MENU: [
                MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['edit_list']}|{KEYBOARD_TEXTS['remove_list']}|{KEYBOARD_TEXTS['back']})$"), list_menu_router),
            ],
            EDIT_LIST_MENU: [
                MessageHandler(filters.Regex(f"^({KEYBOARD_TEXTS['add']}|{KEYBOARD_TEXTS['delete']}|{KEYBOARD_TEXTS['back']})$"), edit_list_menu_router),
            ],
            ADD_SINGER: [
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), back_to_edit_list_menu_handler),
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['delete']}$"), ignore_delete_in_add_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['delete']})$"), save_singer_handler),
            ],
            DELETE_SINGER: [
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), back_to_edit_list_menu_handler),
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['add']}$"), ignore_add_in_delete_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({KEYBOARD_TEXTS['back']}|{KEYBOARD_TEXTS['add']})$"), remove_singer_handler),
            ],
            REMOVE_LIST_CONFIRM: [
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['confirm']}$"), confirm_remove_list_handler),
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['cancel_action']}$"), cancel_remove_list_handler),
            ],
            SET_TIME: [
                MessageHandler(filters.Regex(f"^{KEYBOARD_TEXTS['back']}$"), back_to_main_menu_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_time_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    application.add_handler(conv_handler)
    logger.info("Conversation handler added.")
    logger.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()