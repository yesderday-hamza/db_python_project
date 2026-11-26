import ipaddress

from display import print_table
from vlan_manager import get_vlans, get_vlan, add_vlan, update_vlan, delete_vlan
from subnet_manager import (
    get_subnets,
    get_subnet,
    get_subnets_by_vlan,
    get_subnet_usage,
    add_subnet,
    delete_subnet,
)
from ip_address_manager import (
    VALID_STATUSES,
    get_ips_by_subnet,
    get_ip_by_address,
    get_next_available,
    reserve_ip,
    unreserve_ip,
    why_not_allocatable,
    allocate_ip,
    release_ip,
)
from device_manager import (
    get_devices,
    search_devices,
    get_device,
    get_device_types,
    update_device,
    move_device,
    delete_device,
)

def ask_int(prompt):
    while True:
        value = input(prompt).strip()
        try:
            return int(value)
        except ValueError:
            print("Please enter a number.")

# ---------------------------------------------
#    vlan actions
# ----------------------------------------------
def ask_vlan_id(prompt="VLAN ID: "):
    while True:
        vlan_id = ask_int(prompt)
        if 1 <= vlan_id <= 4094:
            return vlan_id
        print("VLAN ID must be between 1 and 4094.")


def list_vlans():
    print_table(get_vlans(), "VLAN LIST")


def create_vlan():
    vlan_id = ask_vlan_id()
    
    if get_vlan(vlan_id) is not None: 
        print(f"VLAN {vlan_id} already exists.")
        return
    name = input("Name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return
    description = input("Description (optional): ").strip() or None

    if add_vlan(vlan_id, name, description):
        print("VLAN added.")


def edit_vlan():
    vlan_id = ask_vlan_id()
    vlan = get_vlan(vlan_id)
    if vlan is None:
        print("That VLAN doesn't exist.")
        return

    print(f"Editing VLAN {vlan_id} (press Enter to keep the current value)")
    name = input(f"Name [{vlan['vlan_name']}]: ").strip() or vlan["vlan_name"]
    description = input(f"Description [{vlan['description']}]: ").strip()
    if not description:
        description = vlan["description"]

    if update_vlan(vlan_id, name, description):
        print("VLAN updated.")


def remove_vlan():
    vlan_id = ask_vlan_id()
    vlan = get_vlan(vlan_id)
    if vlan is None:
        print("That VLAN doesn't exist.")
        return

    confirm = input(f"Delete VLAN {vlan_id} ({vlan['vlan_name']})? [y/N]: ")
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        return

    if delete_vlan(vlan_id):
        print("VLAN deleted.")

# -----------------------------------------------
#       subnet actions
# --------------------------------------------
def list_subnets():
    print_table(get_subnets(), "SUBNET LIST")


def list_subnets_of_vlan():
    vlan_id = ask_vlan_id()
    vlan = get_vlan(vlan_id)
    if vlan is None:
        print("That VLAN doesn't exist.")
        return
    print_table(get_subnets_by_vlan(vlan_id), f"SUBNETS IN VLAN {vlan_id} ({vlan['vlan_name']})")


def show_usage():
    print_table(get_subnet_usage(), "SUBNET USAGE")


def create_subnet():
    vlan_id = ask_vlan_id("VLAN ID for this subnet: ")
    network = input("Network (e.g. 192.168.60.0/24): ").strip()
    gateway = input("Gateway (Enter = first usable address): ").strip() or None

    ok, message = add_subnet(vlan_id, network, gateway)
    print(message)


def remove_subnet():
    subnet_id = ask_int("Subnet ID: ")
    subnet = get_subnet(subnet_id)
    if subnet is None:
        print("That subnet doesn't exist.")
        return

    label = f"{subnet['network_address']}/{subnet['cidr']}"
    confirm = input(f"Delete subnet {label} and all its IP addresses? [y/N]: ")
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        return

    ok, message = delete_subnet(subnet_id)
    print(message)


#-----------------------------------------
#          ip_address actions
#----------------------------------------
def lookup_ip(text):
    try:
        text = str(ipaddress.IPv4Address(text.strip()))
    except ValueError:
        print("That is not a valid IPv4 address.")
        return None

    ip = get_ip_by_address(text)
    if ip is None:
        print(f"{text} is not in any subnet.")
    return ip


def ask_ip(prompt="IP address: "):
    return lookup_ip(input(prompt))


def pick_next_available():
    subnet_id = ask_int("Subnet ID: ")
    subnet = get_subnet(subnet_id)
    if subnet is None:
        print("That subnet doesn't exist.")
        return None

    ip = get_next_available(subnet_id)
    if ip is None:
        print(f"No available IPs left in {subnet['network_address']}/{subnet['cidr']}.")
    return ip

def list_ips():
    subnet_id = ask_int("Subnet ID: ")
    subnet = get_subnet(subnet_id)
    if subnet is None:
        print("That subnet doesn't exist.")
        return

    status = input(
        "Filter by status (available / allocated / reserved, Enter = all): "
    ).strip().lower() or None
    if status is not None and status not in VALID_STATUSES:
        print("Invalid status.")
        return

    label = f"{subnet['network_address']}/{subnet['cidr']}"
    print_table(get_ips_by_subnet(subnet_id, status), f"IPs IN {label}")


def show_ip():
    ip = ask_ip()
    if ip is None:
        return

    status = ip["status"]
    if ip["ip_address"] == ip["gateway"]:
        status += " (gateway)"

    details = [{
        "IP": ip["ip_address"],
        "Subnet": f"{ip['network_address']}/{ip['cidr']}",
        "Status": status,
        "Device": ip["device_name"],
        "Type": ip["device_type"],
    }]
    print_table(details, "IP DETAILS")


def show_next_available():
    ip = pick_next_available()
    if ip is not None:
        print(f"Next available IP: {ip['ip_address']}")


def allocate():
    text = input("IP address (Enter = next available in a subnet): ").strip()
    ip = lookup_ip(text) if text else pick_next_available()
    if ip is None:
        return

    reason = why_not_allocatable(ip)
    if reason is not None:
        print(reason)
        return

    print(f"Allocating {ip['ip_address']}")
    device_name = input("Device name: ").strip()
    device_type = input("Device type (optional, e.g. server, printer): ").strip() or None

    ok, message = allocate_ip(ip, device_name, device_type)
    print(message)


def release():
    ip = ask_ip()
    if ip is None:
        return

    if ip["status"] == "allocated":
        who = ip["device_name"] or "no device recorded"
        confirm = input(f"Release {ip['ip_address']} ({who})? [y/N]: ")
        if confirm.strip().lower() != "y":
            print("Cancelled.")
            return

    ok, message = release_ip(ip)
    print(message)


def reserve():
    ip = ask_ip()
    if ip is None:
        return
    ok, message = reserve_ip(ip)
    print(message)


def unreserve():
    ip = ask_ip()
    if ip is None:
        return
    ok, message = unreserve_ip(ip)
    print(message)



# --------------------------------------------
#             devices actions
#--------------------------------------------
def ask_device():
    device_id = ask_int("Device ID: ")
    device = get_device(device_id)
    if device is None:
        print("That device doesn't exist.")
    return device


def list_devices():
    device_type = input("Filter by type (Enter = all): ").strip() or None
    print_table(get_devices(device_type), "DEVICE LIST")


def find_devices():
    text = input("Search by device name or IP: ").strip()
    if not text:
        print("Nothing to search for.")
        return
    print_table(search_devices(text), f"DEVICES MATCHING '{text}'")


def show_device():
    device = ask_device()
    if device is None:
        return

    details = [{
        "ID": device["device_id"],
        "Name": device["device_name"],
        "Type": device["device_type"],
        "IP": device["ip_address"],
        "Network": device["network"],
        "VLAN": f"{device['vlan_id']} ({device['vlan_name']})",
        "IP status": device["status"],
    }]
    print_table(details, "DEVICE DETAILS")


def show_device_types():
    print_table(get_device_types(), "DEVICES BY TYPE")


def edit_device():
    device = ask_device()
    if device is None:
        return

    print(f"Editing {device['device_name']} (press Enter to keep the current value)")
    name = input(f"Name [{device['device_name']}]: ").strip() or device["device_name"]
    device_type = input(f"Type [{device['device_type']}]: ").strip() or device["device_type"]

    ok, message = update_device(device["device_id"], name, device_type)
    print(message)


def relocate_device():
    device = ask_device()
    if device is None:
        return

    print(f"{device['device_name']} currently uses {device['ip_address']}")
    text = input("New IP address (Enter = next available in a subnet): ").strip()
    new_ip = lookup_ip(text) if text else pick_next_available()
    if new_ip is None:
        return

    reason = why_not_allocatable(new_ip)
    if reason is not None:
        print(reason)
        return

    confirm = input(
        f"Move {device['device_name']} from {device['ip_address']} "
        f"to {new_ip['ip_address']}? [y/N]: "
    )
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        return

    ok, message = move_device(device, new_ip)
    print(message)


def remove_device():
    device = ask_device()
    if device is None:
        return

    confirm = input(
        f"Remove {device['device_name']} and free {device['ip_address']}? [y/N]: "
    )
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        return

    ok, message = delete_device(device)
    print(message)




#-------------------------------------------
#       Menus
#-----------------------------------------------

def vlan_menu():
    while True:
        print("\n--- VLANs ---")
        print("1. List VLANs")
        print("2. Add VLAN")
        print("3. Edit VLAN")
        print("4. Delete VLAN")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "1":
            list_vlans()
        elif choice == "2":
            create_vlan()
        elif choice == "3":
            edit_vlan()
        elif choice == "4":
            remove_vlan()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def subnet_menu():
    while True:
        print("\n--- Subnets ---")
        print("1. List all subnets")
        print("2. List subnets of a VLAN")
        print("3. Subnet usage")
        print("4. Add subnet")
        print("5. Delete subnet")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "1":
            list_subnets()
        elif choice == "2":
            list_subnets_of_vlan()
        elif choice == "3":
            show_usage()
        elif choice == "4":
            create_subnet()
        elif choice == "5":
            remove_subnet()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")

def ip_menu():
    while True:
        print("\n--- IP addresses ---")
        print("1. List IPs of a subnet")
        print("2. Find an IP address")
        print("3. Next available IP in a subnet")
        print("4. Allocate an IP to a device")
        print("5. Release an IP")
        print("6. Reserve an IP")
        print("7. Unreserve an IP")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "1":
            list_ips()
        elif choice == "2":
            show_ip()
        elif choice == "3":
            show_next_available()
        elif choice == "4":
            allocate()
        elif choice == "5":
            release()
        elif choice == "6":
            reserve()
        elif choice == "7":
            unreserve()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def device_menu():
    while True:
        print("\n--- Devices ---")
        print("1. List devices")
        print("2. Search devices (name or IP)")
        print("3. Device details")
        print("4. Devices by type")
        print("5. Add a device (allocates an IP)")
        print("6. Edit a device")
        print("7. Move a device to another IP")
        print("8. Remove a device")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "1":
            list_devices()
        elif choice == "2":
            find_devices()
        elif choice == "3":
            show_device()
        elif choice == "4":
            show_device_types()
        elif choice == "5":
            allocate()
        elif choice == "6":
            edit_device()
        elif choice == "7":
            relocate_device()
        elif choice == "8":
            remove_device()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")

def main_menu():
    while True:
        print("\n=== IPAM ===")
        print("1. VLANs")
        print("2. Subnets")
        print("3. IP addresses")
        print("4. Devices")
        print("0. Exit")
        choice = input("Choice: ").strip()

        if choice == "1":
            vlan_menu()
        elif choice == "2":
            subnet_menu()
        elif choice == "3":
            ip_menu()
        elif choice == "4":
            device_menu()
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main_menu()
