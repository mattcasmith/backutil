import os, pandas, time, configparser, subprocess, getopt, sys, hashlib

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

class Data:
    def __init__(self):
        self.hashes_df = ""
        self.hash_files_df = ""

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
            print("MCAS Backutil v0.52 | (C) 2021 MattCASmith | MattCASmith.net")
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
def get_prev_hashes(config, data):
    log("Checking old backup hashes...", "Attempt")
    
    # Generate list of current hash files
    hash_files = []
    backup_hash_folder = config.staging_folder + config.computer_name
    for root, directories, filenames in os.walk(backup_hash_folder):
        for filename in filenames: 
            if ".back" in filename:
                hash_files.append(os.path.join(root,filename))
    
    # Only runs if backups need to be rotated - deletes most recent file
    if len(hash_files) >= (config.backups_retained - 1) and (config.backups_rotated == "True"):
        too_many_hashes = len(hash_files) - (config.backups_retained - 1)
        hash_files_df = pandas.DataFrame(data={'file':hash_files,
                                     'age':None })     
        for index, row in hash_files_df.iterrows():
            file_create = os.path.getctime(row[1])
            hash_files_df.iloc[index][0] = file_create
    
        oldest_hash_file = hash_files_df.sort_values(by=['age']).head(too_many_hashes)
        for value in oldest_hash_file['file']:
            oldest_hash_file = value
            command = "del /f /s /q /a " + oldest_hash_file
            subprocess.call(command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
            
        print("Deleted old backup hashes as per rotation policy.")
        log("Old backup hashes deleted.", "Success")
            
    # Gathers hashes from remaining files
    hash_files = []
    previous_hashes = []
    for root, directories, filenames in os.walk(config.staging_folder + config.computer_name):
        for filename in filenames:
            if ".back" in filename:
                hash_files.append(os.path.join(root,filename))
    for hash_file in hash_files:
        current_file = open(hash_file, 'r')
        temp_list = ""
        for line in current_file:
            temp_list = line
        temp_list = temp_list.split(",")
        for previous_hash in temp_list:
            previous_hashes.append(previous_hash)
        current_file.close()
    for index, row in data.hashes_df.iterrows():
        if row[2] in previous_hashes:
            data.hashes_df.iloc[index][3] = "N"
    
    print("Checked old backup hashes.")
    log("Old backup hashes successfully checked.", "Success")

# Main routine - gathers files, adds to 7-Zip, copies to backup directory
def backup(config, data):
    
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

    # Establish Pandas data frame
    data.hashes_df = pandas.DataFrame(data={'backed_up':"N",
                                'file':backup_files,
                                'hash':None,
                                'to_back_up':"Y"})
    
    # Generate hashes
    log("Generating hashes...", "Attempt")
    for index, row in data.hashes_df.iterrows():
        try:
            # Generate file hash
            filename = row[1]
            filename = filename.replace("\\","\\\\")
            sha256_hash = hashlib.sha256()
            with open(filename,"rb") as f:
                for byte_block in iter(lambda: f.read(4096),b""):
                    sha256_hash.update(byte_block)
                hash_output = (sha256_hash.hexdigest())
            data.hashes_df.iloc[index][2] = hash_output
        except:
            msg = "Couldn't generate hash for " + row[1]
            log(msg, "Error")
            data.hashes_df.iloc[index][2] = "Error"
            data.hashes_df.iloc[index][3] = "N"
    print("Generated hashes for backup files.")
    log("Hashes generated successfully.", "Success")
    
    # Get previous hashes if incremental
    if config.incremental == "True":
        try:
            get_prev_hashes(config, data)
        except:
            print("Error checking previous backup hashes.")
            log("Error checking previous backup hashes.", "Failure")
    
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
    log("Copying files...", "Attempt")
    for index, row in data.hashes_df.iterrows():
        if row[3] == "Y":
            backup_path = row[1]
            backup_filename = backup_path.rsplit('\\',1)[1]
            backup_path = backup_path.replace(":","")
            backup_path = backup_path.rsplit('\\',1)[0]
            backup_path = config.staging_folder + config.backup_time + "/" + backup_path
            backup_path = backup_path.replace("\\","/")
            try:
                os.makedirs(backup_path)
            except:
                pass
            copy_command = "robocopy " + "\"" + row[1].rsplit('\\', 1)[0] + "\"" + " " + "\"" + backup_path.replace("/","\\") + "\" \"" + backup_filename + "\"  /NFL /NDL /NJH /NJS /nc /ns /np"
            try:
                output = subprocess.call(copy_command, shell=True, stdout=config.FNULL, stderr=subprocess.STDOUT)
                if output == 1:
                    data.hashes_df.iloc[index][0] = "Y"
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
    
    # Create file listing backed up hashes
    log("Writing hashes...", "Attempt")
    try:
        hashes_file_path = config.staging_folder + config.computer_name + "\\"
        os.mkdir(hashes_file_path)
    except:
        log("Error creating hashes folder (or already exists).", "Error")
    try:
        completed_hashes_file_path = config.staging_folder + config.computer_name + "\\" + config.backup_time + ".back"
        completed_hashes_file = open(completed_hashes_file_path, 'a')
        for index, row in data.hashes_df.iterrows():
            if row[0] == "Y":
                completed_hashes_file.write(row[2] + ",")
        completed_hashes_file.close()
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
        
        # Create table to store files
        backup_files_df = pandas.DataFrame(data={'file':backup_files,
                                     'age':None })
    
        # Add ages to files
        for index, row in backup_files_df.iterrows():
            file_create = os.path.getctime(row[1])
            backup_files_df.iloc[index][0] = file_create
            
        # Identify and remove oldest backup
        oldest_backup = backup_files_df.sort_values(by=['age']).head(config.too_many_backups)
        for value in oldest_backup['file']:
            oldest_backup_file = value
            command = "del /f /s /q /a " + oldest_backup_file
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
    print("MCAS BACKUTIL v0.52")
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
    if config.backups_rotated == "True":
        try:
            check_backups(config)
        except:
            print("Error checking number of previous backups.")
            log("Error checking previous backups.", "Failure")    
    try:
        data = Data()
        backup(config, data)
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
    print("Finished.")
    print("")
      
if __name__ == "__main__": 
    main()