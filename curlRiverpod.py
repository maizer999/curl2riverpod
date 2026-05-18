import re
import os
import json  # Added missing json import
import tkinter as tk
from tkinter import messagebox, ttk

def camel_to_snake(name):
    # Converts PascalCase/camelCase or hyphenated strings cleanly to snake_case
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'[-_\s]+', '_', s2)

def clean_to_pascal(segment):
    words = re.split(r'[-_\s]', segment)
    return "".join(w.capitalize() for w in words if w)

def to_camel_case(text):
    pascal = clean_to_pascal(text)
    return pascal[0].lower() + pascal[1:]

def extract_feature_and_endpoint_from_url(curl_str):
    if not curl_str or "curl" not in curl_str.lower():
        return "BerthShifting", "https://q-pmis2.tabadul.sa/api-gateway/tugspilot/boat-resource"
        
    url_match = re.search(r'(https?://[^\s\'"]+)', curl_str)
    if url_match:
        full_url = url_match.group(1).split('?')[0] 
        segments = [seg for seg in full_url.split('/') if seg and not seg.startswith('http')]
        
        if segments:
            # Safely drop trailing pagination keywords
            if segments[-1].lower() == 'pagination' and len(segments) > 1:
                segments.pop()
                
            if segments[-1].lower() == 'crn' and len(segments) > 1:
                target_segment = segments[-2]
            else:
                target_segment = segments[-1]
                
            return clean_to_pascal(target_segment), full_url
            
    return "BerthShifting", "https://q-pmis2.tabadul.sa/api-gateway/tugspilot/boat-resource"

def get_dart_type(value, key, feature_name):
    if value is None:
        return "dynamic"
    if isinstance(value, bool):
        return "bool?"
    if isinstance(value, int):
        return "int?"
    if isinstance(value, float):
        return "double?"
    if isinstance(value, str):
        return "String?"
    if isinstance(value, list):
        return "List<dynamic>?"
    if isinstance(value, dict):
        return f"{feature_name}{key.capitalize()}?"
    return "dynamic"

def process_generation(raw_feature_name, raw_json, raw_curl_str):
    input_name = raw_feature_name.strip()
    if not input_name:
        messagebox.showerror("Error", "Feature Name cannot be empty.")
        return

    try:
        data = json.loads(raw_json.strip())
    except Exception as e:
        messagebox.showerror("JSON Error", f"Invalid Output JSON format:\n{str(e)}")
        return

    feature_name = clean_to_pascal(input_name)
    snake_name = camel_to_snake(input_name)
    camel_name = to_camel_case(input_name)
    
    # Extract the full clean URL from the curl string
    _, full_url = extract_feature_and_endpoint_from_url(raw_curl_str)
    endpoint_variable = f"'{full_url}'"
    
    # -------------------------------------------------------------
    # SETUP DIRECTORIES STRUCTURE
    # -------------------------------------------------------------
    desktop_dir = os.path.expanduser("~/Desktop")
    feature_root_dir = os.path.join(desktop_dir, snake_name)
    
    models_dir = os.path.join(feature_root_dir, "models")
    services_dir = os.path.join(feature_root_dir, "services")
    notifiers_dir = os.path.join(feature_root_dir, "notifiers")

    # -------------------------------------------------------------
    # 1. MODEL CODE
    # -------------------------------------------------------------
    model_code = f"import 'package:dart_mappable/dart_mappable.dart';\n\n"
    model_code += f"part '{snake_name}_model.mapper.dart';\n\n"
    
    # --- RESPONSE CLASS ---
    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Response with {feature_name}ResponseMappable {{\n"
    model_code += "  final int responseCode;\n  final String responseMessage;\n\n"
    model_code += f"  @MappableField(key: \"data\")\n  final {feature_name}Data? {camel_name}Data;\n\n"
    model_code += f"  {feature_name}Response({{\n    required this.responseCode,\n    required this.responseMessage,\n    this.{camel_name}Data,\n  }});\n}}\n\n"
    
    data_obj = data.get("data", {})
    if isinstance(data_obj, list) and len(data_obj) > 0:
        data_obj = data_obj[0]
    elif not isinstance(data_obj, dict):
        data_obj = {}

    # --- DATA CLASS ---
    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Data with {feature_name}DataMappable {{\n"
    model_code += f"  @MappableField(key: \"content\")\n  final List<{feature_name}Content>? {camel_name}Content;\n"
    model_code += f"  @MappableField(key: \"pageable\")\n  final {feature_name}Pageable? {camel_name}Pageable;\n"
    
    # Always guarantee at least totalElements/totalPages properties to protect empty data blocks from build_runner crash
    if "totalElements" not in data_obj: data_obj["totalElements"] = 0
    if "totalPages" not in data_obj: data_obj["totalPages"] = 1

    for k, v in data_obj.items():
        if k not in ["content", "pageable"]:
            model_code += f"  final {get_dart_type(v, k, feature_name)} {k};\n"
            
    extra_data_keys = [k for k in data_obj.keys() if k not in ["content", "pageable"]]
    
    model_code += f"\n  {feature_name}Data({{\n    this.{camel_name}Content,\n    this.{camel_name}Pageable,\n"
    for k in extra_data_keys:
        model_code += f"    this.{k},\n"
    model_code += "  });\n}\n\n"
    
    # --- CONTENT CLASS ---
    content_list = data_obj.get("content", []) if isinstance(data_obj, dict) else []
    content_obj = {}
    if isinstance(content_list, list) and len(content_list) > 0:
        content_obj = content_list[0] if isinstance(content_list[0], dict) else {}

    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Content with {feature_name}ContentMappable {{\n"
    if content_obj:
        for k, v in content_obj.items():
            model_code += f"  final {get_dart_type(v, k, feature_name)} {k};\n"
        model_code += f"\n  {feature_name}Content({{\n"
        for k in content_obj.keys():
            model_code += f"    this.{k},\n"
        model_code += "  });\n}\n\n"
    else:
        # Avoid generating constructor parameters targeting non-existent fields
        model_code += "  final String? id;\n\n"
        model_code += f"  {feature_name}Content({{\n    this.id,\n  }});\n}}\n\n"
    
    # --- PAGEABLE CLASS ---
    pageable_obj = data_obj.get("pageable", {}) if isinstance(data_obj, dict) else {}
    if not isinstance(pageable_obj, dict): pageable_obj = {}
    
    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Pageable with {feature_name}PageableMappable {{\n"
    if pageable_obj:
        for k, v in pageable_obj.items():
            if k == "unpaged":
                model_code += f"  @MappableField(key: \"unpaged\")\n  final bool? unpaged;\n"
            else:
                model_code += f"  final {get_dart_type(v, k, feature_name)} {k};\n"
        model_code += f"\n  {feature_name}Pageable({{\n"
        for k in pageable_obj.keys():
            model_code += f"    this.{k},\n"
        model_code += "  });\n}"
    else:
        model_code += "  final int? pageNumber;\n\n"
        model_code += f"  {feature_name}Pageable({{\n    this.pageNumber,\n  }});\n}}"

    # -------------------------------------------------------------
    # 2. SERVICE CODE (With final params update)
    # -------------------------------------------------------------
    service_template = """import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:multiple_result/multiple_result.dart';
import '../../../../constants/api_constants.dart';
import '../../../../constants/exceptions/exceptions.dart';
import '../../../../constants/network/network_handler.dart';
import '../models/__SNAKE_NAME___model.dart';

class __FEATURE_NAME__ManagementService {
  Future<Result<__FEATURE_NAME__Response, AppException>> get__FEATURE_NAME__Details({
    required String crn,
    CancelToken? cancelToken,
  }) async {
    final params = {
      "crn": crn,
    };

    try {
      return await safeApiCall(() async {
        final jsonResponse = await NetworkHandler.getRequest(
          headers: await NetworkHandler.getCommonPostHeaders(),
          endpoint: __ENDPOINT_VARIABLE__,
          params: params,
          cancelToken: cancelToken,
        );

        return Success(__FEATURE_NAME__ResponseMapper.fromMap(jsonResponse));
      });
    } catch (e) {
      return Error(e as AppException);
    }
  }
}

final __CAMEL_NAME__ServiceProvider = Provider.autoDispose<__FEATURE_NAME__ManagementService>((ref) {
  return __FEATURE_NAME__ManagementService();
});"""
    service_code = service_template.replace("__FEATURE_NAME__", feature_name).replace("__ENDPOINT_VARIABLE__", endpoint_variable).replace("__SNAKE_NAME__", snake_name).replace("__CAMEL_NAME__", camel_name)

    # -------------------------------------------------------------
    # 3. PROVIDER / NOTIFIER CODE
    # -------------------------------------------------------------
    provider_template = """import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_infinite_scroll_pagination/riverpod_infinite_scroll_pagination.dart';
import 'package:mawani_pmis/utils/extension/cancel_extension.dart';
import 'package:mawani_pmis/utils/extension/result_extension.dart';
import '../../../../../providers/providers.dart';
import '../models/__SNAKE_NAME___model.dart';
import '../services/__SNAKE_NAME___service.dart';

class __FEATURE_NAME__ViewNotifier extends AutoDisposeAsyncNotifier<List<__FEATURE_NAME__Content>>
    with PaginatedDataMixin<__FEATURE_NAME__Content>
    implements PaginatedNotifier<__FEATURE_NAME__Content> {

  @override
  FutureOr<List<__FEATURE_NAME__Content>> build() {
    return init(
      dataFetcher: PaginatedDataRepository(
        fetcher: ({required page, query}) async {
          final crnQuery = ref.watch(searchQueryProvider);

          final result = await ref.watch(__CAMEL_NAME__ServiceProvider).get__FEATURE_NAME__Details(
            crn: crnQuery,
            cancelToken: ref.cancelToken(),
          );

          final response = result.getOrThrowError();

          return PaginatedResponse(
            data: response.__CAMEL_NAME__Data?.__CAMEL_NAME__Content ?? [],
            pagination: Pagination(
              currentPage: page,
              totalNumber: response.__CAMEL_NAME__Data?.totalElements ?? 0,
              lastPage: response.__CAMEL_NAME__Data?.totalPages ?? 1,
            ),
          );
        },
      ),
    );
  }
}

final __CAMEL_NAME__ListNotifierProvider = AsyncNotifierProvider.autoDispose<
    __FEATURE_NAME__ViewNotifier, List<__FEATURE_NAME__Content>>(
  __FEATURE_NAME__ViewNotifier.new,
  name: "__FEATURE_NAME__ListNotifier",
);"""
    provider_code = provider_template.replace("__FEATURE_NAME__", feature_name).replace("__SNAKE_NAME__", snake_name).replace("__CAMEL_NAME__", camel_name)

    # -------------------------------------------------------------
    # WRITE FOLDERS AND FILES
    # -------------------------------------------------------------
    try:
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(services_dir, exist_ok=True)
        os.makedirs(notifiers_dir, exist_ok=True)

        with open(os.path.join(models_dir, f"{snake_name}_model.dart"), "w") as f: 
            f.write(model_code)
        with open(os.path.join(services_dir, f"{snake_name}_service.dart"), "w") as f: 
            f.write(service_code)
        with open(os.path.join(notifiers_dir, f"{snake_name}_notifier.dart"), "w") as f: 
            f.write(provider_code)
        
        messagebox.showinfo("Success", f"🎉 Directory Architecture Created On Desktop!\n\n"
                                       f"Folder: Desktop/{snake_name}/\n"
                                       f"├── models/{snake_name}_model.dart\n"
                                       f"├── services/{snake_name}_service.dart\n"
                                       f"└── notifiers/{snake_name}_notifier.dart")
    except Exception as e:
        messagebox.showerror("File Error", f"Could not create folder architecture:\n{str(e)}")


# --- UI Layout ---
root = tk.Tk()
root.title("Mawani Structured Architecture Folder Generator")
root.geometry("650x750")

main_frame = ttk.Frame(root, padding="15")
main_frame.pack(fill=tk.BOTH, expand=True)

# 1. Curl Input Box
ttk.Label(main_frame, text="1. Paste Your Curl Command String:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 2))
text_curl = tk.Text(main_frame, height=6, font=("Courier", 10), wrap=tk.WORD, borderwidth=2, relief="groove")
text_curl.pack(fill=tk.X, pady=(0, 10))
text_curl.insert("1.0", "curl --location 'https://q-pmis2.tabadul.sa/api-gateway/tugspilot/boat-resource?page=0&size=10'")

# 2. Feature Class Name Layout
ttk.Label(main_frame, text="2. Feature Class Name (Type or click generate from URL):", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(5, 2))

name_frame = ttk.Frame(main_frame)
name_frame.pack(fill=tk.X, pady=(0, 15))

entry_custom_name = ttk.Entry(name_frame, font=("Helvetica", 11))
entry_custom_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

def on_click_parse_name():
    curl_content = text_curl.get("1.0", tk.END).strip()
    predicted_pascal, _ = extract_feature_and_endpoint_from_url(curl_content)
    
    entry_custom_name.delete(0, tk.END)
    entry_custom_name.insert(0, predicted_pascal)

btn_parse_name = ttk.Button(name_frame, text="🔍 Parse from URL", command=on_click_parse_name)
btn_parse_name.pack(side=tk.RIGHT)

on_click_parse_name()

# 3. Payload JSON Input Box
ttk.Label(main_frame, text="3. Paste JSON Output Data Payload Here:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 2))
text_json = tk.Text(main_frame, height=14, font=("Courier", 10), wrap=tk.WORD, borderwidth=2, relief="groove")
text_json.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

dummy_json = '{\n  "responseCode": 200,\n  "responseMessage": "Success",\n  "data": {\n    "content": [],\n    "pageable": {}\n  }\n}'
text_json.insert("1.0", dummy_json)

def on_generate():
    process_generation(
        raw_feature_name=entry_custom_name.get(),
        raw_json=text_json.get("1.0", tk.END),
        raw_curl_str=text_curl.get("1.0", tk.END)
    )

btn_generate = ttk.Button(main_frame, text="🚀 Generate Data Architecture", command=on_generate)
btn_generate.pack(fill=tk.X, ipady=10)

root.mainloop()