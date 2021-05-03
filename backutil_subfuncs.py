import time, sqlite3, hashlib, os, subprocess, colorama
from termcolor import colored


# Print into header
def print_header(header_type, version):
    if header_type == "normal":
        print("")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("MCAS Backutil v" + version + " | (C) 2021 MattCASmith | MattCASmith.net")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Simple utility to back up select files on Windows systems,")
        print("including incremental backup and rotation features.")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("")
    if header_type == "help":
        print("")
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
        print("--threads <no>| -t <no>   | Sets max no. of threads")
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("")


# Add entries to log CSV when required
def log(event_msg, event_cat, version):
    log_file = open('backutil_log.csv', 'a')
    current_time = time.localtime()
    event_date = time.strftime('%Y-%m-%d', current_time)
    event_time = time.strftime('%H:%M:%S', current_time)
    event = event_date + "," + event_time + "," + version + "," + event_cat + "," + event_msg + "\n"
    log_file.write(event)
    if event_cat == "Attempt":
        print("[" + event_date + " " + event_time + "] [ATTEMPT] " + event_msg)
    elif event_cat == "Success":
        print("[" + event_date + " " + event_time + "] [" + colored("SUCCESS", "white", "on_green") + "] " + event_msg)
    elif event_cat == "Warning":
        print("[" + event_date + " " + event_time + "] [" + colored("WARNING", "grey", "on_yellow") + "] " + event_msg)
    elif event_cat == "Failure":
        print("[" + event_date + " " + event_time + "] [" + colored("FAILURE", "white", "on_red") + "] " + event_msg)
    log_file.close()
    
    
# Previous hashes DB management
def manage_previous_db(config, action, version):
    # Open/create DB
    if action == "open":
        log("Opening previous backups DB...", "Attempt", version)
        config.previous_db_conn = sqlite3.connect(config.previous_db_name)
        config.previous_db_cursor = config.previous_db_conn.cursor()
        config.previous_db_cursor.execute("CREATE TABLE IF NOT EXISTS backutil_previous(date TEXT, hash TEXT);")
        log("Previous backups DB opened successfully.", "Success", version)
    # Close DB
    if action == "close":
        log("Closing previous backups DB...", "Attempt", version)
        config.previous_db_conn.close()
        log("Previous backups DB closed successfully.", "Success", version)

        
# Tracker DB management
def manage_tracker_db(config, action, version):
    # Open/create DB
    if action == "open":
        log("Opening tracker DB...", "Attempt", version)
        config.tracker_db_conn = sqlite3.connect(config.tracker_db_name)
        config.tracker_db_cursor = config.tracker_db_conn.cursor()
        config.tracker_db_cursor.execute("CREATE TABLE IF NOT EXISTS backutil_tracker(file TEXT, hash TEXT);")
        log("Tracker DB opened successfully.", "Success", version)
    # Close DB
    if action == "close":
        log("Closing tracker DB...", "Attempt", version)
        config.previous_db_conn.close()
        log("Tracker DB closed successfully.", "Success", version)

        
# Generate hashes
def generate_hashes(procnum, backup_files_thread, return_dict, version):
    colorama.init()
    return_dict_process = {}
    for filename in backup_files_thread:
        try:
            sha256_hash = hashlib.sha256()
            with open(filename,"rb") as f:
                for byte_block in iter(lambda: f.read(65535),b""):
                    sha256_hash.update(byte_block)
                hash_output = (sha256_hash.hexdigest())
                return_dict_process[filename] = hash_output
        except:
            msg = "Couldn't generate hash for " + filename
            log(msg, "Warning", version)
    return_dict[procnum] = return_dict_process


# Copy files to staging folder
def copy_files(procnum, files_to_back_up_process, staging_folder, backup_time, return_dict, version):
    colorama.init()
    FNULL = open(os.devnull, 'w')
    return_dict_process = {}    
    for backup_file in files_to_back_up_process:
        backup_path = backup_file[0]
        backup_filename = backup_path.rsplit('\\',1)[1]
        backup_path = backup_path.replace(":","")
        backup_path = backup_path.rsplit('\\',1)[0]
        backup_path = staging_folder + backup_time + "/" + backup_path
        backup_path = backup_path.replace("\\","/")
        try:
            os.makedirs(backup_path)
        except:
            pass
        copy_command = "robocopy " + "\"" + backup_file[0].rsplit('\\', 1)[0] + "\"" + " " + "\"" + backup_path.replace("/","\\") + "\" \"" + backup_filename + "\"  /NFL /NDL /NJH /NJS /nc /ns /np"
        try:
            output = subprocess.call(copy_command, shell=True, stdout=FNULL, stderr=subprocess.STDOUT)
            if output == 1:
                return_dict_process[backup_file[1]] = "Y"
            else:
                error = "Error copying " + backup_filename
                log(error, "Warning", version)
        except:
            error = "Error copying " + backup_filename
            log(error, "Warning", version)
    return_dict[procnum] = return_dict_process


# If backups require rotation, ignore oldest hash file
def get_prev_hashes(config, version):
    log("Checking old backup hashes...", "Attempt", version)
    
    # Open DB
    manage_previous_db(config, "open", version)
    
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
        log("Old backup hashes deleted.", "Success", version)

    # Close DB
    manage_previous_db(config, "close", version)

    # JOINs previous hashes DB and tracker DB to find files to back up
    query_data = (config.previous_db_name,)
    config.tracker_db_cursor.execute("ATTACH ? as backutil_previous", query_data)
    results = config.tracker_db_cursor.execute("SELECT backutil_tracker.file, backutil_tracker.hash, backutil_previous.date FROM backutil_tracker LEFT JOIN backutil_previous ON backutil_tracker.hash=backutil_previous.hash;")
    for line in results:
        if line[2] == None:
            config.files_to_back_up.append(line)
    
    log("Old backup hashes successfully checked.", "Success", version)