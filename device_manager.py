from database import run_query, run_command, run_transaction
from ip_address_manager import get_ip_by_address, release_ip, why_not_allocatable

_DEVICE_JOINS = """
    FROM devices d
    JOIN ip_addresses i ON i.ip_id = d.ip_id
    JOIN subnets s      ON s.subnet_id = i.subnet_id
    JOIN vlans v        ON v.vlan_id = s.vlan_id
"""



def get_devices(device_type=None):
    sql = (
        """
        SELECT d.device_id, d.device_name, d.device_type,
               i.ip_address,
               CONCAT(s.network_address, '/', s.cidr) AS network,
               v.vlan_name
        """
        + _DEVICE_JOINS
    )
    params = []
    if device_type is not None:
        sql += " WHERE d.device_type = %s"
        params.append(device_type)
    sql += " ORDER BY INET_ATON(i.ip_address)"
    return run_query(sql, tuple(params))


def search_devices(text):
    pattern = f"%{text}%"
    return run_query(
        """
        SELECT d.device_id, d.device_name, d.device_type,
               i.ip_address,
               CONCAT(s.network_address, '/', s.cidr) AS network,
               v.vlan_name
        """
        + _DEVICE_JOINS
        + """
        WHERE d.device_name LIKE %s OR i.ip_address LIKE %s
        ORDER BY INET_ATON(i.ip_address)
        """,
        (pattern, pattern),
    )


def get_device(device_id):
    rows = run_query(
        """
        SELECT d.device_id, d.device_name, d.device_type,
               d.ip_id, i.ip_address, i.status,
               CONCAT(s.network_address, '/', s.cidr) AS network,
               v.vlan_id, v.vlan_name
        """
        + _DEVICE_JOINS
        + " WHERE d.device_id = %s",
        (device_id,),
    )
    return rows[0] if rows else None


def get_device_types():
    """How many devices there are of each type."""
    return run_query(
        """
        SELECT CASE
                   WHEN device_type IS NULL THEN '(none)'
                   ELSE device_type
               END AS device_type,
               COUNT(*) AS devices
        FROM devices
        GROUP BY device_type
        ORDER BY devices DESC, device_type
        """
    )

# ------------------------------------------------------------------
# Changing  (all return (True/False, message))
#
# Creating a device is done by allocate_ip() in ip_address_manager.py,
# because a device cannot exist without an IP and the IP's status must
# change at the same time.
# ------------------------------------------------------------------

def update_device(device_id, name, device_type=None):
    name = (name or "").strip()
    device_type = (device_type or "").strip() or None
    if not name:
        return False, "Device name cannot be empty."
    if len(name) > 100:
        return False, "Device name is too long (max 100 characters)."
    if device_type is not None and len(device_type) > 50:
        return False, "Device type is too long (max 50 characters)."

    ok = run_command(
        "UPDATE devices SET device_name = %s, device_type = %s WHERE device_id = %s",
        (name, device_type, device_id),
    )
    if ok:
        return True, "Device updated."
    return False, "Could not update the device."


def move_device(device, new_ip):
    
    if new_ip["ip_id"] == device["ip_id"]:
        return False, f"{device['device_name']} already uses {new_ip['ip_address']}."

    reason = why_not_allocatable(new_ip)
    if reason is not None:
        return False, reason

    ok = run_transaction(
        [
            (
                "UPDATE ip_addresses SET status = 'available' "
                "WHERE ip_id = %s AND status = 'allocated'",
                (device["ip_id"],),
            ),
            (
                "UPDATE ip_addresses SET status = 'allocated' "
                "WHERE ip_id = %s AND status = 'available'",
                (new_ip["ip_id"],),
            ),
            (
                "UPDATE devices SET ip_id = %s WHERE device_id = %s AND ip_id = %s",
                (new_ip["ip_id"], device["device_id"], device["ip_id"]),
            ),
        ],
        expect_one_row=True,
    )
    if ok:
        return True, (
            f"{device['device_name']} moved from {device['ip_address']} "
            f"to {new_ip['ip_address']}."
        )
    return False, "Could not move the device. An IP may have just changed; check and retry."


def delete_device(device):
    ip = get_ip_by_address(device["ip_address"])
    if ip is None:
        return False, "Could not find the device's IP address."

    ok, message = release_ip(ip)
    if ok:
        return True, f"Device {device['device_name']} removed; {device['ip_address']} is available again."
    return False, message
