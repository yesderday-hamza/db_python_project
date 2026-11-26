
from database import connection_db, run_query,run_transaction


VALID_STATUSES = ("available", "allocated", "reserved")

IP_DETAIL_SQL = """
    SELECT i.ip_id, i.ip_address, i.status, i.subnet_id,
           s.network_address, s.cidr, s.gateway,
           d.device_name, d.device_type
    FROM ip_addresses i
    JOIN subnets s ON s.subnet_id = i.subnet_id
    LEFT JOIN devices d ON d.ip_id = i.ip_id
"""



def get_ips_by_subnet(subnet_id, status=None):
    sql = """
        SELECT i.ip_id, i.ip_address, i.status, d.device_name, d.device_type
        FROM ip_addresses i
        LEFT JOIN devices d ON d.ip_id = i.ip_id
        WHERE i.subnet_id = %s
    """
    params = [subnet_id]
    if status is not None:
        sql += " AND i.status = %s"
        params.append(status)
    sql += " ORDER BY INET_ATON(i.ip_address)"
    return run_query(sql, tuple(params))


def get_ip_by_address(ip_text):
    rows = run_query(IP_DETAIL_SQL + " WHERE i.ip_address = %s", (ip_text,))
    return rows[0] if rows else None


def get_next_available(subnet_id):
    rows = run_query(
        IP_DETAIL_SQL
        + """
        WHERE i.subnet_id = %s AND i.status = 'available'
        ORDER BY INET_ATON(i.ip_address)
        LIMIT 1
        """,
        (subnet_id,),
    )
    return rows[0] if rows else None



def _is_gateway(ip):
    return ip["ip_address"] == ip["gateway"]




def reserve_ip(ip):
    address = ip["ip_address"]
    if ip["status"] != "available":
        return False, f"{address} is {ip['status']}; only available IPs can be reserved."

    ok = run_transaction(
        [(
            "UPDATE ip_addresses SET status = 'reserved' "
            "WHERE ip_id = %s AND status = 'available'",
            (ip["ip_id"],),
        )],
        expect_one_row=True,
    )
    if ok:
        return True, f"{address} reserved."
    return False, f"Could not reserve {address}. It may have just changed; check it and retry."


def unreserve_ip(ip):
    address = ip["ip_address"]
    if _is_gateway(ip):
        return False, f"{address} is the gateway of its subnet and must stay reserved."
    if ip["status"] != "reserved":
        return False, f"{address} is {ip['status']}, not reserved."

    ok = run_transaction(
        [(
            "UPDATE ip_addresses SET status = 'available' "
            "WHERE ip_id = %s AND status = 'reserved'",
            (ip["ip_id"],),
        )],
        expect_one_row=True,
    )
    if ok:
        return True, f"{address} is available again."
    return False, f"Could not update {address}. It may have just changed; check it and retry."


def why_not_allocatable(ip):
    if ip["status"] == "available":
        return None
    extra = " (it is the subnet gateway)" if _is_gateway(ip) else ""
    return f"{ip['ip_address']} is {ip['status']}{extra}; only available IPs can be allocated."


def allocate_ip(ip, device_name, device_type=None):
    address = ip["ip_address"]
    reason = why_not_allocatable(ip)
    if reason is not None:
        return False, reason

    device_name = (device_name or "").strip()
    device_type = (device_type or "").strip() or None
    if not device_name:
        return False, "Device name cannot be empty."
    if len(device_name) > 100:
        return False, "Device name is too long (max 100 characters)."
    if device_type is not None and len(device_type) > 50:
        return False, "Device type is too long (max 50 characters)."

    ok = run_transaction(
        [
            (
                "UPDATE ip_addresses SET status = 'allocated' "
                "WHERE ip_id = %s AND status = 'available'",
                (ip["ip_id"],),
            ),
            (
                "INSERT INTO devices (ip_id, device_name, device_type) "
                "VALUES (%s, %s, %s)",
                (ip["ip_id"], device_name, device_type),
            ),
        ],
        expect_one_row=True,
    )
    if ok:
        return True, f"{address} allocated to {device_name}."
    return False, f"Could not allocate {address}. It may have just changed; check it and retry."


def release_ip(ip):
    address = ip["ip_address"]
    if ip["status"] != "allocated":
        return False, f"{address} is {ip['status']}, not allocated."

    statements = []
    if ip["device_name"] is not None:
        statements.append(
            ("DELETE FROM devices WHERE ip_id = %s", (ip["ip_id"],))
        )
    statements.append(
        (
            "UPDATE ip_addresses SET status = 'available' "
            "WHERE ip_id = %s AND status = 'allocated'",
            (ip["ip_id"],),
        )
    )

    if run_transaction(statements, expect_one_row=True):
        return True, f"{address} released."
    return False, f"Could not release {address}. It may have just changed; check it and retry."
