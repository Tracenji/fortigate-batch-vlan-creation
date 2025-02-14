import requests
import json
import urllib3
import argparse


urllib3.disable_warnings()




fortigate_ip = ''             
api_key = ''  
starting_vlan = 100  
vlan_amount = 10      
dhcp_start = 20      
dhcp_end = 240       
base_ip = '10.10{}.{}.1/24'
interface = 'fortilink'
use_vlan_id_for_dhcp = False
allow_ping = False


parser = argparse.ArgumentParser(description='idk man, variables')
parser.add_argument('--fortigate-ip', '-f', type=str, help='Fortigate IP address')
parser.add_argument('--api-key', '-k', type=str, help='Fortigate API key')
parser.add_argument('--starting-vlan', '-vs', type=int, help='Starting VLAN ID (e.g. 100)')
parser.add_argument('--vlan-amount', '-va', type=int, help='Number of VLANs to create (e.g. 10)')
parser.add_argument('--dhcp-start', '-ds', type=int, help='DHCP range start (e.g. 20)')
parser.add_argument('--dhcp-end', '-de', type=int, help='DHCP range end (e.g. 240)')
parser.add_argument('--base-ip', '-ip', type=str, help='Base IP format for VLANs (e.g. 10.10{}.{}.1/24)')
parser.add_argument('--interface', '-i', type=str, help='Interface name (e.g. "fortilink" or "lan")')
parser.add_argument('--use-vlan-id-for-dhcp', '-uvd', action='store_true', help='Use VLAN ID for the DHCP server ID')
parser.add_argument('--allow-ping', '-ap', action='store_true', help='Allow ping on the interface')
args = parser.parse_args()



if args.fortigate_ip is not None:
    fortigate_ip = args.fortigate_ip
if args.api_key is not None:
    api_key = args.api_key
if args.starting_vlan is not None:
    starting_vlan = args.starting_vlan
if args.vlan_amount is not None:
    vlan_amount = args.vlan_amount
if args.dhcp_start is not None:
    dhcp_start = args.dhcp_start
if args.dhcp_end is not None:
    dhcp_end = args.dhcp_end
if args.base_ip is not None:
    base_ip = args.base_ip
if args.interface is not None:
    interface = args.interface
if args.use_vlan_id_for_dhcp is not None:
    use_vlan_id_for_dhcp = args.use_vlan_id_for_dhcp
if args.allow_ping is not None:
    allow_ping = args.allow_ping


interface_url = f'https://{fortigate_ip}/api/v2/cmdb/system/interface' 
dhcp_url = f'https://{fortigate_ip}/api/v2/cmdb/system.dhcp/server' 


required_vars = {
    'fortigate_ip': fortigate_ip,
    'api_key': api_key,
    'starting_vlan': starting_vlan,
    'vlan_amount': vlan_amount,
    'dhcp_start': dhcp_start,
    'dhcp_end': dhcp_end,
    'base_ip': base_ip,
    'interface': interface
}

arg_shorthands = {
    'fortigate_ip': '-f',
    'api_key': '-k',
    'starting_vlan': '-vs',
    'vlan_amount': '-va',
    'dhcp_start': '-ds',
    'dhcp_end': '-de',
    'base_ip': '-ip',
    'interface': '-i'
}

for var_name, var_value in required_vars.items():
    if not var_value:
        print(f"Error: {var_name} must have a value. Set it using the --{var_name.replace('_', '-')} or {arg_shorthands[var_name]} argument.")
        exit(1)


if '/' not in base_ip:
    print("Error: base_ip must contain a netmask (e.g., '10.10{}.{}.1/24').")
    exit(1)


netmask = int(base_ip.split('/')[1]) 
if netmask < 24: 
    print("Error: base_ip netmask must be at least 24.")
    exit(1)

headers = {
    'Authorization': f'Bearer {api_key}', 
    'Content-Type': 'application/json' 
}


error_descriptions = {
    -5: "A duplicate entry already exists.",
    -1: "Invalid length of value.",
    -2: "Index out of range.",
    -3: "Entry not found.",
    -4: "Maximum number of entries has been reached.",
    -8: "Invalid IP Address.",
    -9: "Invalid IP Netmask.",
    -10: "Invalid gateway address.",
    -14: "Permission denied. Insufficient privileges.",
    -15: "Duplicate entry found.",
    -16: "Blank or incorrect address entry."
}

def create_vlan(vlan_id, ip_subnet): 
    payload = { 
        'name': f'vlan{vlan_id}',
        'vlanid': vlan_id,
        'interface': interface,
        'ip': ip_subnet,
        'vdom': 'root',  
        'allowaccess': 'ping' if allow_ping else '' 
    }
    
    response = requests.post(interface_url, headers=headers, data=json.dumps(payload), verify=False, timeout=10)
    if response.status_code == 200:
        print(f'Successfully created VLAN {vlan_id} with IP {ip_subnet}')
        create_dhcp_server(vlan_id, ip_subnet)
    else:
        error_code = response.json().get('error')
        if error_code == -8:
            error_message = f'Error code {error_code}: Invalid IP Address: {ip_subnet}'
        elif error_code == -9:
            error_message = f'Error code {error_code}: Invalid IP Netmask: {ip_subnet.split("/")[1]}'
        else:
            error_message = error_descriptions.get(error_code, f'Error code {error_code}: {response.text}')
        print(f'Failed to create VLAN {vlan_id}: {error_message}')

def create_dhcp_server(vlan_id, ip_subnet):
    base_ip = ip_subnet.split('/')[0]
    start_ip = base_ip.rsplit('.', 1)[0] + f'.{dhcp_start}'
    end_ip = base_ip.rsplit('.', 1)[0] + f'.{dhcp_end}'
    
    payload = {
        'vdom': 'root',
        'default-gateway': base_ip,
        'dns-service': 'default',
        'interface': f'vlan{vlan_id}',
        'netmask': '255.255.255.0',
        'ip-range': [
            {
                'start-ip': start_ip,
                'end-ip': end_ip
            }
        ]
    }
    
    if use_vlan_id_for_dhcp:
        payload['id'] = vlan_id 

    response = requests.post(dhcp_url, headers=headers, data=json.dumps(payload), verify=False, timeout=10)
    if response.status_code == 200:
        print(f'Successfully created DHCP server for VLAN {vlan_id}')
    else:
        error_code = response.json().get('error')
        if error_code == -8:
            error_message = f'Error code {error_code}: Invalid IP Address: {base_ip}'
        elif error_code == -9:
            error_message = f'Error code {error_code}: Invalid IP Netmask: 255.255.255.0'
        else:
            error_message = error_descriptions.get(error_code, f'Error code {error_code}: {response.text}')
        print(f'Failed to create DHCP server for VLAN {vlan_id}: {error_message}')

def main():
    vlan_range = range(starting_vlan, starting_vlan + vlan_amount)
    for vlan_id in vlan_range:
        x = vlan_id // 100
        y = vlan_id % 100
        ip_subnet = base_ip.format(x, y)
        create_vlan(vlan_id, ip_subnet)

if __name__ == '__main__':
    main()
