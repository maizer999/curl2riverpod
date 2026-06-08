import json
import os
import re
import urllib.request
import ssl

def clean_string(s):
    """Normalizes strings to make matching flexible (ignores case and special characters)."""
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()

def to_camel_case(s):
    """Converts a typical JSON key or text string into standard Dart camelCase."""
    s = re.sub(r'[^a-zA-Z0-9 ]', ' ', s)
    words = s.split()
    if not words:
        return "emptyKey"
    
    camel = words[0].lower() + "".join(w.capitalize() for w in words[1:])
    
    if camel.endswith("id") and len(camel) > 2: camel = camel[:-2] + "Id"
    elif camel.endswith("rid") and len(camel) > 3: camel = camel[:-3] + "Rid"
    elif camel.endswith("no") and len(camel) > 2: camel = camel[:-2] + "No"
    
    return camel

def download_and_localize(api_url, ui_file_path, output_dart_path, class_name="SubPortLocal"):
    print("⏳ Connecting to Tabadul Gateway and downloading localization mappings...")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(
        api_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            json_data = json.loads(response.read().decode('utf-8'))
            print("✅ Successfully downloaded localization map data.")
    except Exception as e:
        print(f"❌ Failed to fetch localization from API: {e}")
        return

    if not os.path.exists(ui_file_path):
        print(f"❌ UI file not found at: {ui_file_path}")
        return
        
    with open(ui_file_path, 'r', encoding='utf-8') as f:
        ui_code = f.read()
        
    ui_titles = re.findall(r'title:\s*"([^"]+)"', ui_code)
    if not ui_titles:
        print("ℹ️ No hardcoded 'title: \"...\"' items found in your specified UI file.")
        return
    
    print(f"🔍 Found {len(ui_titles)} UI attributes. Matching against downloaded map...")

    matched_entries = {}
    updated_ui_code = ui_code
    flat_json = {}

    # Handles nested objects or lists coming from the Tabadul API payload
    def flatten(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    flatten(v)
                else:
                    flat_json[k] = v
        elif isinstance(d, list):
            for item in d:
                flatten(item)

    flatten(json_data)

    for title in ui_titles:
        normalized_title = clean_string(title)
        found = False
        
        for json_key, json_value in flat_json.items():
            if normalized_title == clean_string(json_key) or normalized_title == clean_string(json_value):
                dart_variable_name = to_camel_case(json_key)
                matched_entries[dart_variable_name] = json_value
                
                old_line = f'title: "{title}"'
                new_line = f'title: {class_name}.{dart_variable_name}'
                updated_ui_code = updated_ui_code.replace(old_line, new_line)
                
                print(f"   🎯 Matched: '{title}' -> {class_name}.{dart_variable_name} (\"{json_value}\")")
                found = True
                break
                
        if not found:
            fallback_var = to_camel_case(title)
            matched_entries[fallback_var] = title
            old_line = f'title: "{title}"'
            new_line = f'title: {class_name}.{fallback_var}'
            updated_ui_code = updated_ui_code.replace(old_line, new_line)
            print(f"   ⚠️ No map match for '{title}'. Created default key: {class_name}.{fallback_var}")

    # Build the Dart class content
    dart_class_buffer = f"class {class_name} {{\n"
    for key, val in sorted(matched_entries.items()):
        safe_val = str(val).replace('"', '\\"')
        dart_class_buffer += f'  static const String {key:<25} = "{safe_val}";\n'
    dart_class_buffer += "}\n"

    # Save the file to the Desktop path
    with open(output_dart_path, 'w', encoding='utf-8') as f:
        f.write(dart_class_buffer)
    print(f"\n💾 Saved generated localization keys class to DESKTOP: {output_dart_path}")

    # Update UI file
    with open(ui_file_path, 'w', encoding='utf-8') as f:
        f.write(updated_ui_code)
    print("🚀 UI code updated successfully with localization properties!")


if __name__ == "__main__":
    API_URL = "https://qapigw.tabadul.sa/tabadul/pmis2/mobileapi/lookupmaster/localization/locale-map?module=ALTCNF%2CCCM%2CDMR%2CDMRG%2CDRPT%2CExceptionMessages%2CGENERAL%2CLKP%2CMENU%2CRPA%2CTP%2CT_P%2CUSRMGMT%2CVCOM%2CVVM%2CV_I"
    
    # 1. Update this path to match your actual local layout file location
    UI_FILE = "lib/presentation/widgets/bay_plans_widget.dart" 
    
    # 2. This dynamically targets your system Desktop regardless of Windows/Mac/Linux
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    LOCALIZATION_FILE = os.path.join(desktop_dir, "sub_port_local.dart")

    download_and_localize(API_URL, UI_FILE, LOCALIZATION_FILE, class_name="SubPortLocal")