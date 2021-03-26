# MCAS Backutil v0.61
Python-based utility for backing up files on Windows systems<br />
<a href="https://mattcasmith.net">MattCASmith.net</a> | <a href="https://twitter.com/mattcasmith">@MattCASmith</a>

```diff
- Backutil is a learning/hobby project and some aspects of its code may not follow best
- practices. While you're welcome to use it, you do so at your own risk. Make sure you take
- a manual backup of your files before trying it out, and don't go relying on it to back
- up your production servers.
```

### Introduction

Backutil is a simple, Python-based utility for backing up files from Windows systems to compressed, password-protected local archives. It has features for performing incremental backups and automatically rotating backup files. This is achieved using <code>robocopy</code> and 7-Zip, which must be installed.

To back up your files, simply ensure you have configured Backutil (see below) and run <code>backutil.exe</code> from the Command Prompt or PowerShell. The utility will report on its progress until the backup is successfully completed. More detail can also be found in <code>backutil_log.csv</code>.

<img src="https://mattcasmith.net/wp-content/uploads/2020/12/backutil-1.png">
 
When the utility is finished, you should find your complete backup files in your designated backup folder. The number and size of these backup files can be configured using the incremental backup and rotation settings, which are set in the configuration file or as command line options.

<img src="https://mattcasmith.net/wp-content/uploads/2020/12/backutil-2.png">

As Backutil automatically manages your backup files, it can be configured to run automatically at the desired interval using the Windows Task Scheduler. Backutil's features can be used to generate rolling full or incremental backups as required by your backup objectives and disk size.

#### Testing and limitations

Aside from all the testing that comes naturally during the development process, I have been using Backutil to back up my personal files for the last few months using a Windows scheduled task to run the utility on a weekly basis. My configuration performs incremental backups on a five-file rotation and so far has worked without a hitch, to a level where I occasionally even forgot it was running.

One slight limitation, which will be improved with <a href="#future-development">future development</a>, is the speed of the backup process. My current backups include around 83GB of data (about 50GB once compressed), and the initial "big" backup can take a couple of hours to run. For this reason, I recommend using Backutil to back up a focused set of directories rather than your whole hard drive, at least for the moment.

### Configuration

Backutil can be configured via three main means: a configuration file, a file containing a list of directories to be backed up, and a series of command line options that override other settings. If a configuration file and backup list file are present, Backutil can be run using the following simple command.

```
.\backutil.exe
```

In terms of an installation directory, I put the executable and configuration files in <code>C:\backutil\bin\\</code> and use <code>C:\backutil\\</code> as the staging folder for the temporary files and records. However, you can put these files wherever you like as long as your settings are configured accordingly.

#### Configuration file

Backutil automatically loads settings from a file named <code>config.ini</code>, including the location of the list of directories to back up, folders for backups and temporary files, and incremental backup and rotation options. The configuration file should be located in the same folder as <code>backutil.exe</code>.

The contents of an example configuration file are shown below.

```
[LOCAL]
computer_name = matts-pc
backup_list = backup-list.txt
staging_folder = C:\backutil\
archive_pass = supersecretpassword
incremental = True
rotation = True
retained = 5

[SERVER]
server_directory = D:\backups\
```

The table below sets out what each option in the <code>config.ini</code> configuration file does. Note that all directories supplied via the configuration file must include the trailing backslash.

|**Section** |**Key** |**Purpose** |
|----------- |------- |----------- |
|LOCAL |computer_name |Sets backup folder/record name |
|LOCAL |backup_list |Sets the backup list filename |
|LOCAL |staging_folder |Sets folder for temporary file storage |
|LOCAL |archive_pass |Sets 7-Zip backup file password |
|LOCAL |incremental |Turns incremental backups on/off (True/False) |
|LOCAL |rotation |Turns backup rotation on/off (True/False) |
|LOCAL |retained |Sets number of backups to retain if rotation is on |
|SERVER |server_directory |Sets folder for backup storage |

#### Backup list file

The backup list file is a text file containing a list of directories. When Backutil is run, it will automatically generate a list of files to back up by scanning the contents of these directories and all subdirectories. The format of the backup list file should look something like the example below.

```
C:/Users/Matt/Desktop
C:/Users/Matt/Downloads
C:/Users/Matt/Music/iTunes/iTunes Media/Music
C:/Users/Matt/Pictures
C:/Users/Matt/Videos
```

#### Command line options

Backutil also supports several options if you wish to set certain configuration parameters manually from the Command Prompt or PowerShell. Note that any parameters set via command line options will override the respective parameters in the <code>config.ini</code> configuration file.

|**Short** |**Long** |**Purpose** |
|---- |--------- |------------------------- |
|-h |\-\-help |Displays the help file |
|-n \<name\> |\-\-name \<name\> |Manually sets the backup folder/record name |
|-l \<file\> |\-\-list \<file\> |Manually sets the backup list file |
|-i |\-\-incremental |Manually turns on incremental backups |
|-r \<no\> |\-\-rotate \<no\> |Manually turns on backup rotation and sets number of backups |

The following command shows an example of how the command line options may be used.

```
.\backutil.exe -n matts-pc -l locations.txt -i -r 5
```
Running Backutil with the options above will save backup files to a folder called <code>matts-pc</code> (note that this folder name is also how previous backups are tracked). The list of directories to back up files from will be retrieved from <code>locations.txt</code>. Backups will be incremental (only changed files will be backed up each time Backutil runs) and five previous backups will be retained.

### Changelog

|**Date** |**Version** |**Changes** |
|----------- |------- |----------- |
|26/03/2021 |v0.61 |Implemented SQLite and other speed improvements:<br />- All data processed using SQLite<br />- Hashes generated using bigger file chunks<br />- File size cut by 80 per cent due to Pandas removal |
|19/02/2021 |v0.52 |Small bug fixes and improvements from v0.51:<br />- 7-Zip file now generated directly in destination folder<br />- Hash file now only generated after successful backup<br />- Blank line at end of backup list file no longer required<br />- Help page consistent with online documentation<br />- Fixed --help and --incremental arguments |

### Future development

My determination to build a minimum viable product before the end of 2020 means that I have a backlog of bug fixes and new features to add during 2021. These include:

* **Speed/efficiency improvements** - As it stands, Backutil generates hashes and copies files via some fairly simple logic. As a next step I hope to implement a multithreading solution to process multiple files at once and reduce the time taken to perform each backup.

* **Remote backups** - You'll notice that some parts of Backutil use terminology associated with remote backups (for example, the Server section in the configuration file). This is because Backutil could originally be configured to use WinSCP to send backup files to a remote server. This has been removed for the initial release, but I hope to reinstate it in a future version.

* **Graphical user interface (GUI)** - I've played around with Python GUIs a couple of times before, but have never had a script worth implementing one for. Depending on time limitations, I might develop a GUI for Backutil to increase ease of use for less experienced users.

* **Inconsistencies and bug fixes** - The more time you spend with a piece of code, the more flaws you find in it. I'm sure I'll spot plenty to fix along the way.

Have you got more ideas for new Backutil features? Or have you found bugs that you think I haven't? Please <a href="mailto:mattcasmith@protonmail.com">send me an email</a> to let me know so I can add them to the development backlog.

If you're interested in the project, check back regularly to see if there are new releases. I'll also announce any updates on <a target="_blank" href="https://twitter.com/mattcasmith">my Twitter account</a> and on <a href="https://mattcasmith.net">my blog</a>.
