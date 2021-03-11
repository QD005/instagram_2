#pylint:disable=W0311
from . import __version__
from .util import parse_cli_args
from .util import highlight_print
from .util import save_account_progress
from .settings import Settings
from .print_log_writer import log_following_num
from .exceptions import InstaPyError
import os
import logging
from .browser import set_selenium_local_session
from logging.handlers import RotatingFileHandler
from .settings import localize_path
from .login_util import login_user
from .file_manager import get_logfolder
from .file_manager import get_workspace
from .print_log_writer import log_follower_num
#from platform import python_version
from sys import platform
try:
    from pyvirtualdisplay import Display
except ModuleNotFoundError:
    pass

class InstaPy:
    """Class to be instantiated to use the script"""

    def __init__(
        self,
        username: str = None,
        password: str = None,
        nogui: bool = False,
        selenium_local_session: bool = True,
        browser_profile_path: str = None,
        page_delay: int = 25,
        show_logs: bool = True,
        headless_browser: bool = False,
        proxy_username: str = None,
        proxy_password: str = None,
        proxy_address: str = None,
        proxy_port: str = None,
        disable_image_load: bool = False,
        multi_logs: bool = True,
        log_handler=None,  # TODO function type ?
        geckodriver_path: str = None,
        split_db: bool = False,
        bypass_security_challenge_using: str = "email",
        security_codes: int = 0000,
        #want_check_browser: bool = True,
        browser_executable_path: str = None,
        geckodriver_log_level: str = "info",  # "info" by default
    ):
        ##print("InstaPy Version: {}".format(__version__))
        cli_args = parse_cli_args()
        username = cli_args.username or username
        password = cli_args.password or password
        page_delay = cli_args.page_delay or page_delay
        headless_browser = cli_args.headless_browser or headless_browser
        proxy_address = cli_args.proxy_address or proxy_address
        proxy_port = cli_args.proxy_port or proxy_port
        disable_image_load = cli_args.disable_image_load or disable_image_load
        split_db = cli_args.split_db or split_db
        #want_check_browser = cli_args.want_check_browser or want_check_browser

        Settings.InstaPy_is_running = True
        # workspace must be ready before anything
        if not get_workspace():
            raise InstaPyError("Oh no! I don't have a workspace to work at :'(")

        # virtual display to hide browser (not supported on Windows)
        self.nogui = nogui
        if self.nogui:
            if not platform.startswith("win32"):
                self.display = Display(visible=0, size=(800, 600))
                self.display.start()
            else:
                raise InstaPyError("The 'nogui' parameter isn't supported on Windows.")

        self.browser = None
        self.aborting = False
        self.page_delay = page_delay
        self.disable_image_load = disable_image_load
        self.bypass_security_challenge_using = bypass_security_challenge_using
        self.security_codes = security_codes
        
        self.username = os.environ.get("INSTA_USER") or username
        self.password = os.environ.get("INSTA_PW") or password

        Settings.profile["name"] = self.username

                # assign logger
        self.show_logs = show_logs
        Settings.show_logs = show_logs or None
        self.multi_logs = multi_logs
        self.logfolder = get_logfolder(self.username, self.multi_logs)
        self.logger = self.get_instapy_logger(self.show_logs, log_handler)

        if selenium_local_session:
            self.browser, err_msg = set_selenium_local_session(
                proxy_address,
                proxy_port,
                proxy_username,
                proxy_password,
                headless_browser,
                browser_profile_path,
                disable_image_load,
                page_delay,
                geckodriver_path,
                browser_executable_path,
                self.logfolder,
                self.logger,
                geckodriver_log_level,
            )
            if len(err_msg) > 0:
                raise InstaPyError(err_msg)
        
        # choose environment over static typed credentials
        self.username = os.environ.get("INSTA_USER") or username
        self.password = os.environ.get("INSTA_PW") or password

        Settings.profile["name"] = self.username

        self.split_db = split_db
        if self.split_db:
            Settings.database_location = localize_path(
                "db", "instapy_{}.db".format(self.username)
            )

        #self.want_check_browser = want_check_browser
        self.proxy_address = proxy_address
        
        self.show_logs = show_logs
        Settings.show_logs = show_logs or None
        
        self.liked_img = 0
        self.already_liked = 0
        self.liked_comments = 0
        self.commented = 0
        self.replied_to_comments = 0
        self.followed = 0
        self.already_followed = 0
        self.unfollowed = 0
        self.followed_by = 0
        self.following_num = 0
        self.inap_img = 0
        self.not_valid_users = 0
        self.video_played = 0
        self.already_Visited = 0
        self.stories_watched = 0
        self.reels_watched = 0

        self.multi_logs = multi_logs
        self.logfolder = get_logfolder(self.username, self.multi_logs)
        self.logger = self.get_instapy_logger(self.show_logs, log_handler)
        
    def login(self):
            """Used to login the user either with the username and password"""
            # InstaPy uses page_delay speed to implicit wait for elements,
            # here we're decreasing it to 5 seconds instead of the default 25
            # seconds to speed up the login process.
            #
            # In short: default page_delay speed took 25 seconds trying to locate
            # every element, now it's taking 5 seconds.
            temporary_page_delay = 5
            self.browser.implicitly_wait(temporary_page_delay)
    
            if not login_user(
                self.browser,
                self.username,
                self.password,
                self.logger,
                self.logfolder,
                self.proxy_address,
                self.bypass_security_challenge_using,
                self.security_codes,
                #self.want_check_browser,
            ):
                message = (
                    "Unable to login to Instagram! "
                    "You will find more information in the logs above."
                )
                highlight_print(self.username, message, "login", "critical", self.logger)
    
                self.aborting = True
                return self
    
            # back the page_delay to default, or the value set by the user
            self.browser.implicitly_wait(self.page_delay)
            message = "Logged in successfully!"
            highlight_print(self.username, message, "login", "info", self.logger)
            # try to save account progress
            try:
                save_account_progress(self.browser, self.username, self.logger)
            except Exception as e:
                # Comment:
                # Saw this error:
                # "TypeError: window._sharedData.entry_data.ProfilePage is undefined"
                # when IG deleted a pic or video due community guidelines, then the
                # FF session shows a different page that interrupts the normal flow.
                self.logger.warning(
                    "Unable to save account progress, skipping data update \n\t{}".format(
                        str(e).encode("utf-8")
                    )
                )
    
            # logs only followers/following numbers when able to login,
            # to speed up the login process and avoid loading profile
            # page (meaning less server calls)
            self.followed_by = log_follower_num(self.browser, self.username, self.logfolder)
            self.following_num = log_following_num(
                self.browser, self.username, self.logfolder
            )
    
            return self
    def get_instapy_logger(self, show_logs: bool, log_handler=None):
            """
            Handles the creation and retrieval of loggers to avoid
            re-instantiation.
            """
    
            existing_logger = Settings.loggers.get(self.username)
            if existing_logger is not None:
                return existing_logger
            else:
                # initialize and setup logging system for the InstaPy object
                logger = logging.getLogger(self.username)
                logger.setLevel(logging.DEBUG)
                # log name and format
                general_log = "{}general.log".format(self.logfolder)
                file_handler = logging.FileHandler(general_log)
                # log rotation, 5 logs with 10MB size each one
                file_handler = RotatingFileHandler(
                    general_log, maxBytes=10 * 1024 * 1024, backupCount=5
                )
                file_handler.setLevel(logging.DEBUG)
                extra = {"username": self.username}
                logger_formatter = logging.Formatter(
                    "%(levelname)s [%(asctime)s] [%(username)s]  %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
                file_handler.setFormatter(logger_formatter)
                logger.addHandler(file_handler)
    
                # add custom user handler if given
                if log_handler:
                    logger.addHandler(log_handler)
    
                if show_logs is True:
                    console_handler = logging.StreamHandler()
                    console_handler.setLevel(logging.DEBUG)
                    console_handler.setFormatter(logger_formatter)
                    logger.addHandler(console_handler)
    
                logger = logging.LoggerAdapter(logger, extra)
    
                Settings.loggers[self.username] = logger
                Settings.logger = logger
                return logger
                       