# web-update-check
Web Update Checker Tool with Telegram Integration:

Stay effortlessly informed about website changes with our versatile Web Update Checker tool. 
Whether you're monitoring "zalando.de" or any other site, this tool provides tailored functions to track updates efficiently.
Receive notifications and alerts seamlessly through our Telegram bot interface, simplifying user interaction.

## Key Features:
+ Customizable functions to monitor various websites, including "zalando.de".
+ Integration with a Telegram bot for convenient user input and output.
+ Automatically store and restore assignments, ensuring continuity even if the bot is restarted.
+ Optional Whitelist feature, allowing only authorized users or admins to access the tool.

## Setup:
To use the Web Update Checker tool, create "auth.py" in the bots main directory.
Make sure you have the following settings configured in "auth.py":
```
Token = Your SECRET_TOKEN as String
Admin = Your ChatID as int
Whitelist = Your Setting as bool
```
### Dependencies:
Using "requests", "json" and "telegram" libraries.

## Additional Features: 

### 👢 Zalando Parser:
Specifically designed parser to check the availability of sizes on Zalando.de. Automatically monitor the availability of sizes for selected products.
Receive timely notifications when the sizes you're interested in become available.

### 🔍 Search for String Feature:
Adapt the tool to various websites by searching for specific strings in the website's content. By specifying particular strings or keywords, you can track changes like product availability, blog updates, event dates, or any other crucial information.

### 💾 Persistence Feature:
Experience uninterrupted workflow with the Persistence feature. Your bot now stores Assignments and seamlessly restores them automatically. Plus, the bot saves statistics at regular 60-second intervals, ensuring no data is lost.

### 🔒 Whitelist Feature:
Enhance your bot's security with the Whitelist feature. When enabled, only registered users or the admin can access the bot. The admin can add users using the command /admin_join {ChatID}. By default, this feature is turned off, ensuring flexible access control.

### 🛠️ Admin Interface:
Empower administrators with the Admin Interface, a hassle-free way to manage essential functions on the go, without the need for direct server access. Use commands like /admin_purge to clean up, /admin_delete to remove specific items, and /admin_join to effortlessly add users to the whitelist.
