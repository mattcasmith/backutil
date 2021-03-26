import os, time, configparser, subprocess, getopt, sys, hashlib, sqlite3

class Config:
    def __init__(self, computer_name, backup_list_file, staging_folder, archive_password, server_directory, backups_rotated, backups_retained, too_many_backups, incremental):
        self.computer_name = computer_name
        self.backup_list_file = backup_list_file
        self.staging_folder = staging_folder
        self.archive_password = archive_password
        self.server_directory = server_directory
        self.backups_rotated = backups_rotated
        self.backups_retained = backups_retained
        self.too_many_backups = too_many_backups
        self.incremental = incremental
        self.FNULL = open(os.devnull, 'w')
        self.backup_time = ""
        self.previous_db_conn = ""
        self.previous_db_name = computer_name + ".sqlite"
        self.previous_db_cursor = ""
        self.tracker_db_conn = ""
        self.tracker_db_name = ":memory:"
        self.tracker_db_cursor = ""
        self.files_to_back_up = []
        self.files_backed_up = []

# Previous hashes DB management
def manage_previous_db(config, action):
    # Open/create DB
    if action == "open":
        config.previous_db_conn = sqlite3.connect(config.previous_db_name)
        config.previous_db_cursor = config.previous_db_conn.cursor()
        config.previous_db_cursor.execute("CREATE TABLE IF NOT EXISTS backutil_previous(date TEXT, hash TEXT);")
    # Close DB
    if action == "close":
        config.previous_db_conn.close()
        
# Tracker DB management
def manage_tracker_db(config, action):
    # Open/create DB
    if action == "open":
        config.tracker_db_conn = sqlite3.connect(config.tracker_db_name)
        config.tracker_db_cursor = config.tracker_db_conn.cursor()
        config.tracker_db_cursor.execute("CREATE TABLE IF NOT EXISTS backutil_tracker(file TEXT, hash TEXT);")
    # Close DB
    if action == "close":
        config.previous_db_conn.close()

# Parse command line options
def cl_options(config):
    options_s = "hn:l:ir:"
    options_l = ["name=", "list=", "incremental", "rotate=", "help"]
    full_cmd_arguments = sys.argv
    argument_list = full_cmd_arguments[1:]
    arguments, values = getopt.getopt(argument_list, options_s, options_l)
    for current_argument, current_value in arguments:
        if current_argument in ("-h", "--help"):
            print("")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("MCAS Backutil v0.61 | (C) 2021 MattCASmith | MattCASmith.net")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("Simple utility to back up select files on Windows systems,")
            print("including incremental backup and rotation features.")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("FILES")
            print("Config file | config.ini       | Sets configuration options")
            print("Backup list | *.txt            | Sets folders to back up")
            print("Log file    | backutil_log.csv | Event log for utility use")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("COMMAND LINE OPTIONS")
            print("Where applicable, these options override config.ini")
            print("--help        | -h        | Displays help and information")
            print("--name <name> | -n <name> | Sets backup folder/record name")
            print("--list <file> | -l <file> | Sets backup list file")
            print("--incremental | -i        | Turns on incremental backups")
            print("--rotate <no> | -r <no>   | Sets no. of backups to rotate")
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print("")
            sys.exit()
        if current_argument in ("-n", "--name"):
            config.computer_name = current_value
            log("Backup name set via command line arguments.", "Success")
        if current_argument in ("-l", "--list"):
            config.backup_list_file = current_value
            log("Backup list file set via command line arguments.", "Success")
        if current_argument in ("-i", "--incremental"):
            config.incremental = "True"
            log("Incremental backup set via command line arguments.", "Success")
        if current_argument in ("-r", "--rotate"):
            config.backups_rotated = "True"
            config.backups_retained = int(current_value)
            log("Backup rotation set via command line arguments.", "Success")
    
# Add entries to log CSV when required
def log(event_msg, event_cat):
    log_file = open('backutil_log.csv', 'a')
    current_time = time.localtime()
    event_date = time.strftime('%Y-%m-%d', current_time)
    event_time = time.strftime('%H:%M:%S', current_time)
    event = event_date + "," + event_time + "," + event_cat + "," + event_msg + "\n"
    log_file.write(event)
    log_file.close()
    
# Checks number of backups and sets number to delete after backup
def check_backups(config):
    log("Checking number of previous backups...", "Attempt")
    
    # Get list of existing backup files
    backup_files = []
    backup_directory = config.server_directory + config.computer_name
    for root, directories, filenames in os.walk(backup_directory):
        for filename in filenames: 
            if ".7z" in filename:
                backup_files.append(os.path.join(root,filename))
                
    # If more than enough, set flag
    if len(backup_files) >= (config.backups_retained - 1):
        config.too_many_backups = len(backup_files) - (config.backups_retained - 1)
    
    print("Checked number of previous backups.")
    log("Previous backups checked.", "Success")

# If backups require rotation, ignore oldest hash file
def get_prev_hashes(config):
    log("Checking old backup hashes...", "Attempt")
    
    # Open DB
    manage_previous_db(config, "open")
    
    # Generate list of current backups in DB
    backup_dates=[]
    db_dates = config.previous_db_cursor.execute("SELECT DISTINCT date FROM backutil_previous ORDER BY date ASC;")
    for date in db_dates:
        backup_dates.append(date[0])
    
    # Only runs if backups need to be rotated - deletes DB entries for oldest backup
    if len(backup_dates) > (config.backups_retained - 1) and (config.backups_rotated == "True"):
        query_data = (str(backup_dates[0]),)
        config.previous_db_cursor.execute("DELETE FROM backutil_previous WHERE date = ?;", query_data)
        config.previous_db_conn.commit()
            
        print("Deleted old backup hashes as per rotation policy.")
        log("Old backup hashes deleted.", "Success")

    # Close DB
    manage_previous_db(config, "close")

    # JOINs previous hashes DB and tracker DB to find files to back up
    query_data = (config.previous_db_name,)
    config.tracker_db_cursor.execute("ATTACH ? as backutil_previous", query_data)
    results = config.tracker_db_cursor.execute("SELECT backutil_tracker.file, backutil_tracker.hash, backutil_previous.date FROM backutil_tracker LEFT JOIN backutil_previous ON backutil_tracker.hash=backutil_previous.hash;")
    for line in results:
        if line[2] == None:
            config.files_to_back_up.append(line)
    
    print("Checked old backup hashes.")
    log("Old backup hashes successfully checked.", "Success")

# Main routine - gathers files, adds to 7-Zip, copies to backup directory
def backup(config):
    
    # Get list of files and folders
    log("Getting backup list...", "Attempt")
    backup_list = []
    backup_list_file = open(config.backup_list_file)
    for line in backup_list_file:
        if line[-1] == "\n":
            backup_list.append(line[:-1])
        else:
            backup_list.append(line)
    backup_list_file.close()
    print("Read list of directories to back up.")
    log("Backup list read successfully.", "Success")

    # Generate list of all files/folders
    log("Scanning files...", "Attempt")
    backup_files = []
    for folder in backup_list:
        for root, directories, filenames in os.walk(folder):
            for filename in filenames: 
                backup_files.append(os.path.join(root,filename))
    print("Generated list of files to back up.")
    log("File list generated successfully.", "Success")
    
    # Generate hashes
    for filename in backup_files:
        try:
            sha256_hash = hashlib.sha256()
            with open(filename,"rb") as f:
                for byte_block in iter(lambda: f.read(65535),b""):
                    sha256_hash.update(byte_block)
                hash_output = (sha256_hash.hexdigest())
            query_data = (filename, hash_output,)
            config.tracker_db_cursor.execute("INSERT INTO backutil_tracker (file, hash) VALUES (?, ?);", query_data)
        except:
            msg = "Couldn't generate hash for " + filename
            log(msg, "Error")
    config.tracker_db_conn.commit()
    print("Generated hashes for backup files.")
    log("Hashes generated successfully.", "Success")

    # Get previous hashes if incremental
    if config.incremental == "True":
        try:
            get_prev_hashes(config)
        except:
            print("Error checking previous backup hashes.")
            log("Error checking previous backup hashes.", "Failure")
    else:
        results = config.tracker_db_cursor.execute("SELECT file, hash, 'None' AS date FROM backutil_tracker;")
        for line in results:
            config.files_to_back_up.append(line)
    
    # Create staging folder and copy files, make list
    current_time = time.localtime()
    config.backup_time = time.strftime('%Y-%m-%d-%H%M', current_time)

    log("Creating backup and session folders...", "Attempt")
    try:
        os.mkdir(config.staging_folder)
    except:
        log("Error creating backup folder (or already exists).", "Error")
    try:
        os.mkdir(config.staging_folder + config.backup_time)
    except:
        log("Error creating session folder (or already exists).", "Error")
    print("Created temporary folder to copy files.")
    log("Folders created.", "Success")
    
    print("Copying files...")
    log("Copying files...", "Attempt")#
    for backup_file in config.files_to_back_up:
        backup_path = backup_file[0]
        backup_filename = backup_path.rsplit('\\',1)[1]
        backup_path = backup_path.replace(":","")
        backup_path = backup_path.rsplit('\\',1)[0]
        backup_path = config.staging_folder + config.backup_time + "/" + backup_path
        backup_path = backup_path.replace("\\","/")
        try:
            os.makedirs(backup_path)
        except:
            pass
        copy_command = "robocopy " + "\"" + backup_file[0].rsplit('\\', 1)[0] + "\"" + " " + "\"" + backup_path.replace("/","\\") + "\" \"" + backup_filename + "\"  /NFL /NDL /NJH /NJS /nc /ns /np"
        try:
            output = subprocess.call(copy_command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
            if output == 1:
                config.files_backed_up.append(backup_file[1])
            else:
                error = "Error copying " + backup_path + "/" + backup_filename
                log(error, "Error")
        except:
            error = "Error copying " + backup_path + "/" + backup_filename
            print(error)
            log(error, "Error")
    print("Finished copying files.")              
    log("Finished copying files.", "Success")

    # Archive and password protect .7z
    log("Creating .7z archive...", "Attempt")
    command = "7z a -t7z -mhc=on -mhe=on -mmt \"" + config.server_directory + config.computer_name + "\\" + config.backup_time + ".7z\" " + config.staging_folder + config.backup_time +" -p" + config.archive_password
    subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
    print("Created 7-Zip archive.")
    log("7z archive created.", "Success")

    # Write backed up hashes to DB
    log("Writing hashes...", "Attempt")
    try:
        manage_previous_db(config, "open")
        for backed_up_file in config.files_backed_up:
            query_data = (config.backup_time, backed_up_file)
            config.previous_db_cursor.execute("INSERT INTO backutil_previous (date, hash) VALUES (?, ?);", query_data)
        config.previous_db_conn.commit()
        manage_previous_db(config, "close")
        print("Finished writing hashes.")              
        log("Finished writing hashes.", "Success")
    except:
        log("Error writing hashes.", "Error")

# Deletes temporary files
def delete_temp(config):
    # Delete folder on client machine
    log("Deleting temporary files...", "Attempt")
    try:
        command = "rmdir /s /q " + "\"" + config.staging_folder + config.backup_time + "\""
        subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
    except:
        pass
    print("Deleted temporary files.")
    log("Temporary files successfully deleted.", "Success")
    
# If backups require rotation, delete the oldest backup
def rotate_backups(config):
    log("Deleting old backups in line with rotation configuration...", "Attempt") 
    
    # Only runs if backups need to be rotated    
    if config.too_many_backups > 0:
        
        # Get list of existing backup files
        backup_files = []
        backup_directory = config.server_directory + config.computer_name
        for root, directories, filenames in os.walk(backup_directory):
            for filename in filenames: 
                if ".7z" in filename:
                    backup_files.append(os.path.join(root,filename))

        # Get ages and add to dictionary
        backup_files_dic = {}
        for backup_file in backup_files:
            file_create = os.path.getctime(backup_file)
            backup_files_dic[backup_file] = file_create
            
        # Identify and remove oldest backup
        oldest_backup = sorted(backup_files_dic.items(), key = lambda kv: kv[1])[0]
        command = "del /f /s /q /a " + oldest_backup[0]
        subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
            
        print("Old backups deleted in line with rotation configuration.")
        log("Old backups deleted in line with rotation configuration.", "Success")  
            
    else:
        print("No backup rotation required.")
        log("No backup rotation required.", "Success")        
     
# Main routine
def main():
    # Print intro text
    print("")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("MCAS BACKUTIL v0.61")
    print("7-Zip must be installed")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("")
    try:
        log("Loading configuration...", "Attempt")
        config_file = configparser.ConfigParser()
        config_file.sections()
        config_file.read('config.ini')
        computer_name = str(config_file['LOCAL']['computer_name'])
        backup_list_file = str(config_file['LOCAL']['backup_list'])
        staging_folder = str(config_file['LOCAL']['staging_folder'])
        archive_password = str(config_file['LOCAL']['archive_pass'])
        incremental = str(config_file['LOCAL']['incremental'])
        server_directory = str(config_file['SERVER']['server_directory'])
        backups_rotated = str(config_file['LOCAL']['rotation'])
        backups_retained = int(config_file['LOCAL']['retained'])
        too_many_backups = 0
        config = Config(computer_name, backup_list_file, staging_folder, archive_password, server_directory, backups_rotated, backups_retained, too_many_backups, incremental)
        print("Loaded configuration from config.ini.")
        log("Configuration loaded successfully.", "Success")
    except:
        print("Failed due to error loading configuration.")
        log("Error loading configuration.", "Failure")
        sys.exit()
    try:
        cl_options(config)
    except:
        print("Failed due to invalid command line arguments.")
        log("Invalid command line arguments.", "Failure")
        sys.exit()
    try:
        manage_tracker_db(config, "open")
    except:
        print("Error creating tracker DB in memory.")
        log("Error creating tracker DB in memory.", "Failure")  
        sys.exit()
    if config.backups_rotated == "True":
        try:
            check_backups(config)
        except:
            print("Error checking number of previous backups.")
            log("Error checking previous backups.", "Failure")    
    try:
        backup(config)
    except:
        print("Failed due to error during backup.")
        log("Error during backup.", "Failure")   
        sys.exit()
    try:
        delete_temp(config)
    except:
        print("Failed due to error deleting temporary files.")
        log("Error deleting temporary files.", "Failure")
    if config.backups_rotated == "True":
        try:
            rotate_backups(config)
        except:
            print("Error deleting previous backups.")
            log("Error deleting previous backups.", "Failure")   
    try:
        manage_tracker_db(config, "close")
    except:
        print("Error closing tracker DB.")
        log("Error creating tracker DB.", "Failure")  
    print("Finished.")
    print("")
      
if __name__ == "__main__": 
    main()