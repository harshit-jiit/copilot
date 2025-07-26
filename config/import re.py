import re 

l1  = [
    r"^http?://localhost(:\d+)?$",
    r"^http?://[\w\-]+\.localhost(:\d+)?$",
    r"^http?://[\d.]+\.nip\.io(:\d+)?$",  # Matches any IP with nip.io
    r"^http?://[\w\-]+\.[\d.]+\.nip\.io(:\d+)?$",  # Subdomains with IP.nip.io
    r"^http?://[\d.]+(\.\d+)*\.[\d.]+(\.\d+)*(:\d+)?$",  # Direct IP addresses
]
ip_ad = "http://gym1.192.168.1.100.nip.io:8080"

# check ip address
def check_ip_address(ip_address):
    for pattern in l1:
        if re.match(pattern, ip_address):
            print(f"Matched pattern: {pattern}")
            return True
    return False

# Test the function
if __name__ == "__main__":
    if check_ip_address(ip_ad):
        print(f"{ip_ad} is a valid IP address or domain.")
    else:
        print(f"{ip_ad} is NOT a valid IP address or domain.")