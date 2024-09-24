import os
import requests
from bs4 import BeautifulSoup
import platform
import tarfile
import time
import asyncio
import aiohttp
import re
import subprocess
import random
import sys
import shutil
import zipfile
import warnings

# Suppress all DeprecationWarnings - compatability reasons. (also hacky)
warnings.filterwarnings("ignore", category=DeprecationWarning)

def clear_console():
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

def console_header():
    print("\n" + "*"*100)
    print("Mirror Selected".center(100))
    print("https://softwareupdate.vmware.com/cds/vmw-desktop/ws/".center(100))
    print("*"*100 + "\n")

async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.text() if response.status == 200 else None

async def fetch_versions():
    base_url = "https://softwareupdate.vmware.com/cds/vmw-desktop/ws/"
    async with aiohttp.ClientSession() as session:
        main_page = await fetch_url(session, base_url)

        if main_page is None:
            print("Failed to retrieve the page.")
            return []

        soup = BeautifulSoup(main_page, "html.parser")
        version_links = [link['href'] for link in soup.find_all('a', href=True) if link['href'].endswith('/')]

        installers = []
        print("Parsing release versions... Please Wait.")
        time.sleep(2)

        tasks = []
        for version in version_links:
            version_url = f"{base_url}{version}"
            tasks.append(fetch_version_details(session, version_url, installers))

        await asyncio.gather(*tasks)
        
        installers.sort(key=lambda x: list(map(int, re.findall(r'\d+', x))))  # Sort by version numbers
        return installers

async def fetch_version_details(session, version_url, installers):
    version_page = await fetch_url(session, version_url)
    if version_page is None:
        return

    version_soup = BeautifulSoup(version_page, "html.parser")
    subdirectory = next((link['href'] for link in version_soup.find_all('a', href=True) if link['href'] != '../' and link['href'].endswith('/')), None)

    if subdirectory:
        subdirectory_url = f"{version_url}{subdirectory}"
        subdirectory_page = await fetch_url(session, subdirectory_url)

        if subdirectory_page:
            subdirectory_soup = BeautifulSoup(subdirectory_page, "html.parser")
            windows_dir = next((link['href'] for link in subdirectory_soup.find_all('a', href=True) if 'windows' in link['href']), None)

            if windows_dir:
                windows_url = f"{subdirectory_url}{windows_dir}"
                windows_page = await fetch_url(session, windows_url)

                if windows_page:
                    windows_soup = BeautifulSoup(windows_page, "html.parser")
                    core_dir = next((link['href'] for link in windows_soup.find_all('a', href=True) if 'core' in link['href']), None)

                    if core_dir:
                        core_url = f"{windows_url}{core_dir}"
                        core_page = await fetch_url(session, core_url)

                        if core_page:
                            core_soup = BeautifulSoup(core_page, "html.parser")
                            for file_link in core_soup.find_all('a', href=True):
                                file_href = file_link['href']
                                if file_href.endswith('.exe.tar'):
                                    installers.append(file_href.split('/')[-1])  # Store only the file name

def display_menu(installers):
    if not installers:
        print("No installers available for installation.")
        return

    print("\n" + "="*100)
    print("Select an installer to download:".center(100))
    print("="*100)

    # Add "Show All" as the first option
    print("1. Show All")
    
    # Show last 6 versions
    last_versions = installers[-6:] if len(installers) >= 6 else installers
    for idx, installer in enumerate(last_versions):
        print(f"{idx + 2}. {installer}")

    print("="*100)

    # Set default choice to the latest version
    choice = input(f"Select Installer [Latest: {len(last_versions) + 1}]: ") or str(len(last_versions) + 1)

    if choice == '1':  # Show all
        clear_console()
        console_header()
        display_full_menu(installers)  # Function to show full menu
        return None
    elif choice.isdigit() and 1 <= int(choice) <= len(last_versions) + 1:
        selected_installer = last_versions[int(choice) - 2] if int(choice) > 1 else None
    else:
        print("Invalid choice.")
        return None

    return selected_installer

def display_splash():
    print(r"             __    __                 __    __           _        _        _   _             ")
    print(r" /\   /\/\/\/ / /\ \ \__ _ _ __ ___  / / /\ \ \___  _ __| | _____| |_ __ _| |_(_) ___  _ __  ")
    print(r" \ \ / /    \ \/  \/ / _` | '__/ _ \ \ \/  \/ / _ \| '__| |/ / __| __/ _` | __| |/ _ \| '_ \ ")
    print(r"  \ V / /\/\ \  /\  / (_| | | |  __/  \  /\  / (_) | |  |   <\__ \ || (_| | |_| | (_) | | | |")
    print(r"   \_/\/    \/\/  \/ \__,_|_|  \___|   \/  \/ \___/|_|  |_|\_\___/\__\__,_|\__|_|\___/|_| |_|")
    print(r"                                                                                             ")
    print(r"   _         _            ___ _           _                                                  ")
    print(r"  /_\  _   _| |_ ___     / _ (_)_ __ __ _| |_ ___                                            ")
    print(r" //_\\| | | | __/ _ \   / /_)/ | '__/ _` | __/ _ \                                           ")
    print(r"/  _  \ |_| | || (_) | / ___/| | | | (_| | ||  __/                                           ")
    print(r"\_/ \_/\__,_|\__\___/  \/    |_|_|  \__,_|\__\___|                    --whale linguini       ")
    print(r"----------------------------------------------------------------------_________________------")
    print(r"")

def display_full_menu(installers):
    print("\n" + "="*100)
    print("All available installers:".center(100))
    print("="*100)

    for idx, installer in enumerate(installers):
        print(f"{idx + 1}. {installer}")

    print("="*100)

def download_and_extract(installer):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    version_match = re.match(r'VMware-workstation-(\d+\.\d+\.\d+)-(\d+)\.exe\.tar', installer)
    if not version_match:
        print(f"Invalid installer format: {installer}")
        return

    version, build = version_match.groups()
    
    tar_url = f"https://softwareupdate.vmware.com/cds/vmw-desktop/ws/{version}/{build}/windows/core/{installer}"
    tar_path = os.path.join(script_dir, installer)

    print("\n" + "-"*100)
    print(f"Downloading {installer}".center(100))
    print("You must display patience now...".center(100))
    print("-"*100 + "\n")
    print("Wait.")
    
    response = requests.get(tar_url)
    if response.status_code == 200:
        with open(tar_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded to {tar_path}")

        print(f"Extracting {tar_path}...")
        time.sleep(1)
        with tarfile.open(tar_path) as tar:
            tar.extractall(path=script_dir)
        print("")
        print("Extraction complete!")
        time.sleep(0.5)
        
        os.remove(tar_path)
        
        extracted_exe = None
        for file_name in os.listdir(script_dir):
            if file_name.endswith(".exe") and "VMware-workstation" in file_name:
                extracted_exe = os.path.join(script_dir, file_name)
                break
        
        if extracted_exe:
            prompt_install(extracted_exe)
        else:
            print("Failed to find the extracted .exe file.")
    else:
        print(f"Failed to download {installer}. Status code: {response.status_code}")


def run_unlocker():
    repo_url = "https://github.com/DrDonk/unlocker"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    extract_dir = os.path.join(script_dir, 'tmp')

    os.makedirs(extract_dir, exist_ok=True)
    download_and_extract_latest_release(repo_url, extract_dir)

def prompt_install(extracted_exe):
    def process_string(input_str):
        filename = os.path.basename(input_str)
        #print("Full path:", input_str)
        #print("Filename extracted:", filename)
        
        trimmed_str = filename[19:]
        result_str = trimmed_str[:2]
        
        check_codes_15 = [
            "FU512-2DG1H-M85QZ-U7Z5T-PY8ZD",
            "CU3MA-2LG1N-48EGQ-9GNGZ-QG0UD",
            "GV7N2-DQZ00-4897Y-27ZNX-NV0TD",
            "YZ718-4REEQ-08DHQ-JNYQC-ZQRD0",
            "GZ3N0-6CX0L-H80UP-FPM59-NKAD4",
            "YY31H-6EYEJ-480VZ-VXXZC-QF2E0",
            "ZG51K-25FE1-H81ZP-95XGT-WV2C0",
            "VG30H-2AX11-H88FQ-CQXGZ-M6AY4",
            "CU7J2-4KG8J-489TY-X6XGX-MAUX2",
            "FY780-64E90-0845Z-1DWQ9-XPRC0",
            "UF312-07W82-H89XZ-7FPGE-XUH80",
            "AA3DH-0PYD1-0803P-X4Z7V-PGHR4"
        ]
        
        check_codes_16 = [
            "YA7RA-F6Y46-H889Z-LZMXZ-WF8UA",
            "ZV7HR-4YX17-M80EP-JDMQG-PF0RF",
            "UC3XK-8DD1J-089NP-MYPXT-QGU80",
            "GV100-84W16-M85JP-WXZ7E-ZP2R6",
            "YF5X2-8MW91-4888Y-DNWGC-W68TF",
            "AY1XK-0NG5P-0855Y-K6ZXG-YK0T4"
        ]
        
        check_codes_17 = [
            "MC60H-DWHD5-H80U9-6V85M-8280D",
            "4A4RR-813DK-M81A9-4U35H-06KND",
            "NZ4RR-FTK5H-H81C1-Q30QH-1V2LA",
            "JU090-6039P-08409-8J0QH-2YR7F",
            "4Y09U-AJK97-089Z0-A3054-83KLA",
            "4C21U-2KK9Q-M8130-4V2QH-CF810",
            "HY45K-8KK96-MJ8E0-0UCQ4-0UH72",
            "JC0D8-F93E4-HJ9Q9-088N6-96A7F",
            "NG0RK-2DK9L-HJDF8-1LAXP-1ARQ0",
            "0U2J0-2E19P-HJEX1-132Q2-8AKK6"
        ]

        if result_str == "15":
            selected_code = random.choice(check_codes_15)
        elif result_str == "16":
            selected_code = random.choice(check_codes_16)
        elif result_str == "17":
            selected_code = random.choice(check_codes_17)
        else:
            selected_code = "Placeholder 4"

        return filename, result_str, selected_code

    filename, result_str, code = process_string(extracted_exe)
    
    cmd = [extracted_exe, "/s", f'/v"/qn EULAS_AGREED=1 SERIALNUMBER={code} AUTOSOFTWAREUPDATE=0"']
    cmd_str = " ".join(cmd)
    cmd_display = f'/s /v"/qn EULAS_AGREED=1 SERIALNUMBER={code} AUTOSOFTWAREUPDATE=0"'
    
    print("\n" + "-"*100)
    print("Download and Extraction Complete!".center(100))
    print(f"Filename: {filename}".center(100))
    print(f"Serial Key: {result_str}.xx KEY: {code}".center(100))
    print(f"Command: {cmd_display}".center(100))
    print("-"*100 + "\n")
    
    do_install = input("Do auto-install? (y/n): ")
    if do_install.lower() == "y":
        print("Doing Install. Wait.")
        subprocess.run(cmd_str, shell=True)
        print("Installation Complete.")

        # Prompt to download and run the unlocker
        do_unlock = input("Would you like to download and run the unlocker to unlock VMware? (y/n): ")
        if do_unlock.lower() == "y":
            run_unlocker()
        else:
            print("Unlocker was not run.")
    else:
        print("No Install.")

def run_unlocker():
    repo_url = "https://github.com/DrDonk/unlocker"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    extract_dir = os.path.join(script_dir, 'tmp')

    os.makedirs(extract_dir, exist_ok=True)
    download_and_extract_latest_release(repo_url, extract_dir)

def download_and_extract_latest_release(repo_url, extract_to):
    print("\n" + "="*100)
    print("VMWare Unlocker".center(100))
    print("="*100 + "\n")
    print("Starting unlock process.")
    print("")
    api_url = repo_url.replace('https://github.com/', 'https://api.github.com/repos/') + '/releases/latest'
    response = requests.get(api_url)
    response.raise_for_status()
    release_info = response.json()

    zip_url = None
    for asset in release_info['assets']:
        if asset['name'].endswith('.zip'):
            zip_url = asset['browser_download_url']
            break

    if not zip_url:
        raise Exception("No .zip file found in the latest release.")

    zip_filename = os.path.join(extract_to, 'unlocker_latest.zip')
    print(f"Downloading:\n{zip_url}\n")
    with requests.get(zip_url, stream=True) as r:
        r.raise_for_status()
        with open(zip_filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    print(f"Download Complete: {zip_filename}\n")

    print(f"Extracting {zip_filename} to:\n{extract_to}\n")
    with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    os.remove(zip_filename)
    print(f"Extraction Complete. {zip_filename} has been removed.\n")

    unlock_exe_path = os.path.join(extract_to, 'windows', 'unlock.exe')
    status_exe_path = os.path.join(extract_to, 'windows', 'check.exe')
    if os.path.exists(unlock_exe_path):
        print("-" * 100)
        print(f"Running {unlock_exe_path}".center(100))
        print("-" * 100)
        subprocess.run([unlock_exe_path], check=True)
        print("")
        print("Verifying")
        print("")
        subprocess.run([status_exe_path], check=True)
        print("\n" + "-" * 100)
        print("Unlocking completed.".center(100))
        print("-" * 100 + "\n")
    else:
        raise Exception(f"{unlock_exe_path} not found. Cannot execute unlock.exe.")

print("\nFinished!")
print("You have pirate! Enjoy Bounty.")

def main():
    clear_console()
    display_splash()
    console_header()
    installers = asyncio.run(fetch_versions())
    selected_installer = display_menu(installers)
    if selected_installer:
        download_and_extract(selected_installer)

if __name__ == "__main__":
    main()
