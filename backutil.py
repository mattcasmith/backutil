import os, time, configparser, subprocess, getopt, sys, multiprocessing, colorama
from backutil_subfuncs import log, manage_previous_db, manage_tracker_db, generate_hashes, copy_files, get_prev_hashes, print_header

version = "0.70"

class Config:
    def __init__(self, computer_name, backup_list_file, staging_folder, archive_password, server_directory, backups_rotated, backups_retained, too_many_backups, incremental, max_threads):
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
        self.max_threads = max_threads


# Parse command line options
def cl_options(config):
    log("Reading command line arguments...", "Attempt", version)
    options_s = "hn:l:ir:t:"
    options_l = ["name=", "list=", "incremental", "rotate=", "help", "threads="]
    full_cmd_arguments = sys.argv
    argument_list = full_cmd_arguments[1:]
    arguments, values = getopt.getopt(argument_list, options_s, options_l)
    for current_argument, current_value in arguments:
        if current_argument in ("-h", "--help"):
            print_header("help", version)
            sys.exit()
        if current_argument in ("-n", "--name"):
            config.computer_name = current_value
            log("Backup name set via command line arguments.", "Success", version)
        if current_argument in ("-l", "--list"):
            config.backup_list_file = current_value
            log("Backup list file set via command line arguments.", "Success", version)
        if current_argument in ("-i", "--incremental"):
            config.incremental = "True"
            log("Incremental backup set via command line arguments.", "Success", version)
        if current_argument in ("-r", "--rotate"):
            config.backups_rotated = "True"
            config.backups_retained = int(current_value)
            log("Backup rotation set via command line arguments.", "Success", version)
        if current_argument in ("-t", "--threads"):
            config.max_threads = current_value
            log("Maximum threads set via command line arguments.", "Success", version)
    log("Command line arguments read successfully.", "Success", version)
    

# Checks number of backups and sets number to delete after backup
def check_backups(config):
    log("Checking number of previous backups...", "Attempt", version)
    
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
    
    log("Previous backups checked successfully.", "Success", version)


# Main routine - gathers files, adds to 7-Zip, copies to backup directory
def backup(config):
    
    # Get list of files and folders
    log("Getting backup list...", "Attempt", version)
    backup_list = []
    backup_list_file = open(config.backup_list_file)
    for line in backup_list_file:
        if line[-1] == "\n":
            backup_list.append(line[:-1])
        else:
            backup_list.append(line)
    backup_list_file.close()
    log("Backup list read successfully.", "Success", version)

    # Generate list of all files/folders
    log("Generating list of files in backup directories...", "Attempt", version)
    backup_files = []
    for folder in backup_list:
        for root, directories, filenames in os.walk(folder):
            for filename in filenames: 
                backup_files.append(os.path.join(root,filename))
    log("File list generated successfully.", "Success", version)
    
    log("Generating hashes for backup files...", "Attempt", version)
    
    # Split backup_files and generate hashes in multiple subprocesses
    split_backup_files = (backup_files[i::config.max_threads] for i in range(config.max_threads))
    process_container = []
    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    x = 1
    for backup_files_thread in split_backup_files:
        name = "Process-" + str(x)
        process = multiprocessing.Process(target=generate_hashes, name=name, args=(x, backup_files_thread, return_dict, version,))
        process_container.append(process)
        process.start()
        x += 1
    for process in process_container:
        process.join()
    for process in process_container:
        if process.exitcode == 0:
            continue
        else:
            log("Hash generation thread failed.", "Failure", version)
            sys.exit()
    
    # Add output from subprocesses to tracker DB
    combined_dict = {}
    for dictionary in return_dict.values():
        for key, value in dictionary.items():
            combined_dict[key] = value
    for key, value in combined_dict.items():
        query_data = (key, value,)
        config.tracker_db_cursor.execute("INSERT INTO backutil_tracker (file, hash) VALUES (?, ?);", query_data)
    config.tracker_db_conn.commit()
    
    log("Hashes generated successfully.", "Success", version)
    
    # Get previous hashes if incremental
    if config.incremental == "True":
        try:
            get_prev_hashes(config, version)
        except:
            log("Error checking previous backup hashes.", "Failure", version)
    else:
        results = config.tracker_db_cursor.execute("SELECT file, hash, 'None' AS date FROM backutil_tracker;")
        for line in results:
            config.files_to_back_up.append(line)
    
    # Create staging folder and copy files, make list
    current_time = time.localtime()
    config.backup_time = time.strftime('%Y-%m-%d-%H%M', current_time)

    log("Creating backup and session folders...", "Attempt", version)
    try:
        os.mkdir(config.staging_folder)
    except:
        log("Error creating backup folder (or already exists).", "Warning", version)
    try:
        os.mkdir(config.staging_folder + config.backup_time)
    except:
        log("Error creating session folder (or already exists).", "Warning", version)
    log("Backup and session folders created successfully.", "Success", version)
    
    log("Copying files to session folder...", "Attempt", version)
        
    # Split files to be backed up and copy in several subprocesses
    split_files_to_back_up = (config.files_to_back_up[i::config.max_threads] for i in range(config.max_threads))
    process_container = []
    manager = ""
    return_dict = ""
    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    x = 1
    for files_to_back_up_thread in split_files_to_back_up:
        name = "Process-" + str(x)
        process = multiprocessing.Process(target=copy_files, name=name, args=(x, files_to_back_up_thread, config.staging_folder, config.backup_time, return_dict, version,))
        process_container.append(process)
        process.start()
        x += 1
    for process in process_container:
        process.join()
    for process in process_container:
        if process.exitcode == 0:
            continue
        else:
            log("File copy thread failed.", "Failure", version)
            sys.exit()

    # Recombine subprocess output (successfully copied files) ready to add to previous DB
    combined_dict = {}
    for dictionary in return_dict.values():
        for key, value in dictionary.items():
            combined_dict[key] = value
                       
    log("Files copied to session folder successfully.", "Success", version)

    # Archive and password protect .7z
    log("Creating .7z archive...", "Attempt", version)
    command = "7z a -t7z -mhc=on -mhe=on -mmt=" + str(config.max_threads) + " \"" + config.server_directory + config.computer_name + "\\" + config.backup_time + ".7z\" " + config.staging_folder + config.backup_time +" -p" + config.archive_password
    subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
    log("7z archive created.", "Success", version)

    # Write backed up hashes to DB
    log("Writing hashes to DB...", "Attempt", version)
    try:
        manage_previous_db(config, "open", version)
        for key, value in combined_dict.items():
            query_data = (config.backup_time, key)
            config.previous_db_cursor.execute("INSERT INTO backutil_previous (date, hash) VALUES (?, ?);", query_data)
        config.previous_db_conn.commit()
        manage_previous_db(config, "close", version)             
        log("Hashes written to DB successfully.", "Success", version)
    except:
        log("Error writing hashes to DB.", "Warning", version)


# Deletes temporary files
def delete_temp(config):
    # Delete folder on client machine
    log("Deleting temporary files from session folder...", "Attempt", version)
    try:
        command = "rmdir /s /q " + "\"" + config.staging_folder + config.backup_time + "\""
        subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
    except:
        pass
    log("Temporary files deleted successfully.", "Success", version)
    
    
# If backups require rotation, delete the oldest backup
def rotate_backups(config):
    log("Deleting previous backups in line with rotation configuration...", "Attempt", version) 
    
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
            
        log("Previous backups deleted in line with rotation configuration.", "Success", version)  
            
    else:
        log("No backup rotation required.", "Success", version)        
     
        
# Main routine
def main():
    print_header("normal", version)
    colorama.init()
    try:
        log("Loading configuration...", "Attempt", version)
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
        max_threads = int(config_file['LOCAL']['max_threads'])
        too_many_backups = 0
        config = Config(computer_name, backup_list_file, staging_folder, archive_password, server_directory, backups_rotated, backups_retained, too_many_backups, incremental, max_threads)
        log("Configuration loaded successfully.", "Success", version)
    except:
        log("Error loading configuration.", "Failure", version)
        sys.exit()
    try:
        cl_options(config)
    except:
        log("Invalid command line arguments.", "Failure", version)
        sys.exit()
    try:
        manage_tracker_db(config, "open", version)
    except:
        log("Error creating tracker DB in memory.", "Failure", version)  
        sys.exit()
    if config.backups_rotated == "True":
        try:
            check_backups(config)
        except:
            log("Error checking previous backups.", "Failure", version)    
    try:
        backup(config)
    except:
        log("Error during backup.", "Failure", version)
        try:
            delete_temp(config)
        except:
            log("Error deleting temporary files.", "Failure", version)
        sys.exit()
    try:
        delete_temp(config)
    except:
        log("Error deleting temporary files.", "Failure", version)
    if config.backups_rotated == "True":
        try:
            rotate_backups(config)
        except:
            log("Error deleting previous backups.", "Failure", version)   
    try:
        manage_tracker_db(config, "close", version)
    except:
        log("Error creating tracker DB.", "Failure", version)  
    log("Finished.", "Success", version)
    print("")
     
    
if __name__ == "__main__": 
    multiprocessing.freeze_support()
    main()