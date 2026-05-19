import re
import os
import json
import tkinter as tk
from tkinter import messagebox, ttk


def camel_to_snake(name):
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
    if not curl_str:
        return "VesselTimeStamp", "https://qapigw.tabadul.sa/tabadul/pmis2/vesselvoyage/v2/vessel-time-stamp/pagination"
        
    url_match = re.search(r'(https?://[^\s\'"]+)', curl_str)
    if url_match:
        full_url = url_match.group(1).split('?')[0] 
        segments = [seg for seg in full_url.split('/') if seg and not seg.startswith('http')]
        
        if segments:
            ignored_endpoints = ['pagination', 'crn', 'list', 'search', 'filter']
            while segments and segments[-1].lower() in ignored_endpoints:
                segments.pop()
            
            if segments:
                target_segment = segments[-1]
                if re.match(r'^v\d+$', target_segment.lower()) and len(segments) > 1:
                    target_segment = segments[-2]
                    
                return clean_to_pascal(target_segment), full_url
                
    return "VesselTimeStamp", "https://qapigw.tabadul.sa/tabadul/pmis2/vesselvoyage/v2/vessel-time-stamp/pagination"

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
    views_dir = os.path.join(feature_root_dir, "views")

    # -------------------------------------------------------------
    # 1. MODEL CODE
    # -------------------------------------------------------------
    model_code = f"import 'package:dart_mappable/dart_mappable.dart';\n\n"
    model_code += f"part '{snake_name}_model.mapper.dart';\n\n"
    
    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Response with {feature_name}ResponseMappable {{\n"
    model_code += "  final int responseCode;\n  final String responseMessage;\n\n"
    model_code += f"  @MappableField(key: \"data\")\n  final {feature_name}Data? {camel_name}Data;\n\n"
    model_code += f"  {feature_name}Response({{\n    required this.responseCode,\n    required this.responseMessage,\n    this.{camel_name}Data,\n  }});\n}}\n\n"
    
    data_obj = data.get("data", {})
    if isinstance(data_obj, list) and len(data_obj) > 0:
        data_obj = data_obj[0]
    elif not isinstance(data_obj, dict):
        data_obj = {}

    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Data with {feature_name}DataMappable {{\n"
    model_code += f"  @MappableField(key: \"content\")\n  final List<{feature_name}Content>? {camel_name}Content;\n"
    model_code += f"  @MappableField(key: \"pageable\")\n  final {feature_name}Pageable? {camel_name}Pageable;\n"
    
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
        model_code += "  final String? id;\n\n"
        model_code += f"  {feature_name}Content({{\n    this.id,\n  }});\n}}\n\n"
    
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
    # 2. SERVICE CODE
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
    # 4. VIEW / UI CODE GENERATION
    # -------------------------------------------------------------
    dynamic_ui_fields = ""
    if content_obj:
        for k in content_obj.keys():
            if k == "id": continue
            readable_label = k.replace('_', ' ').title()
            dynamic_ui_fields += f"                        LabelValue(\n                            label: \"{readable_label}\",\n                            value: data.{k} ?? \"-\"),\n"
    else:
        dynamic_ui_fields = f"                        LabelValue(\n                            label: \"Title\",\n                            value: \"-\"),\n"

    view_template = """import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mawani_pmis/features/common/widgets/dynamic_common_card.dart';
import 'package:riverpod_infinite_scroll_pagination/riverpod_infinite_scroll_pagination.dart';
import 'package:mawani_pmis/features/common/widgets/common_background.dart';
import 'package:mawani_pmis/features/common/widgets/common_no_data_widget.dart';
import 'package:mawani_pmis/features/common/widgets/common_app_bar.dart';
import 'package:mawani_pmis/features/common/widgets/common_circular_progress.dart';
import 'package:mawani_pmis/features/common/widgets/common_error_widget.dart';
import 'package:mawani_pmis/features/common/widgets/common_search_widget.dart';
import 'package:mawani_pmis/constants/app_local.dart';
import '../../../../routes/router.gr.dart';
import '../../../user_management/common/model/service_enum.dart';
import '../notifiers/__SNAKE_NAME___notifier.dart';
import '../models/__SNAKE_NAME___model.dart';

@RoutePage()
class __FEATURE_NAME__ListView extends StatelessWidget {
  const __FEATURE_NAME__ListView({super.key});

  @override
  Widget build(BuildContext context) {
    return CommonBackground(
      appBar: const CommonAppBar(
        appBarTitle: ServiceEnum.vesseltimestampManagement.getListTitle(),
      ),
      body: Column(
        children: [
          const CommonSearchWidget(noFilter: true),
          Expanded(
            child: Consumer(
              builder: (context, ref, child) {
                return PaginatedListView<__FEATURE_NAME__Content>(
                  state: ref.watch(__CAMEL_NAME__ListNotifierProvider),
                  notifier: ref.read(__CAMEL_NAME__ListNotifierProvider.notifier),
                  itemBuilder: (context, data) {
                    return CommonDynamicCard(
                      fields: [
__UI_DYNAMIC_FIELDS__                      ],
                      onTap: () {
                        context.navigateTo(
                            __FEATURE_NAME__DetailsRoute(id: data.id ?? 0));
                      },
                    );
                  },
                  emptyListBuilder: (context) => const CommonNoDataWidget(),
                  loadingBuilder:
                      (BuildContext context, Pagination pagination) {
                    return getCircularProgress(pagination.currentPage);
                  },
                  errorBuilder: (context, error, stackTrace) {
                    return CommonErrorWidget(
                      error,
                      reload: () {
                        ref.invalidate(__CAMEL_NAME__ListNotifierProvider);
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}"""
    view_code = view_template.replace("__FEATURE_NAME__", feature_name).replace("__SNAKE_NAME__", snake_name).replace("__CAMEL_NAME__", camel_name).replace("__UI_DYNAMIC_FIELDS__", dynamic_ui_fields)

    # -------------------------------------------------------------
    # WRITE FOLDERS AND FILES
    # -------------------------------------------------------------
    try:
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(services_dir, exist_ok=True)
        os.makedirs(notifiers_dir, exist_ok=True)
        os.makedirs(views_dir, exist_ok=True)

        with open(os.path.join(models_dir, f"{snake_name}_model.dart"), "w") as f: 
            f.write(model_code)
        with open(os.path.join(services_dir, f"{snake_name}_service.dart"), "w") as f: 
            f.write(service_code)
        with open(os.path.join(notifiers_dir, f"{snake_name}_notifier.dart"), "w") as f: 
            f.write(provider_code)
        with open(os.path.join(views_dir, f"{snake_name}_list_view.dart"), "w") as f: 
            f.write(view_code)
        
        messagebox.showinfo("Success", f"🎉 Complete Directory Architecture Created On Desktop!\n\n"
                                       f"Folder: Desktop/{snake_name}/\n"
                                       f"├── models/{snake_name}_model.dart\n"
                                       f"├── services/{snake_name}_service.dart\n"
                                       f"├── notifiers/{snake_name}_notifier.dart\n"
                                       f"└── views/{snake_name}_list_view.dart")
    except Exception as e:
        messagebox.showerror("File Error", f"Could not create folder architecture:\n{str(e)}")


# --- UI Layout ---
root = tk.Tk()
root.title("Structured Curl Architecture Folder Generator")
root.geometry("800x900")

# ── Color palette ──────────────────────────────────
PRIMARY    = "#006782"
BG         = "#e8f4f8"
TEXT_BG    = "#ffffff"
TEXT_FG    = "#002a36"
LABEL_FG   = "#ffffff"
BTN_ACTIVE = "#004f63"
# ───────────────────────────────────────────────────

root.configure(bg=PRIMARY)

_icon_data = """iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAA8klEQVR4nO3Yyw2DQBAEUcJ2YM7P
9hEhGfZfM73d0gRQD057HJ7nTd/r/Wm+tOuJTosxIzoNxsr4UAhEeBgIOhxDoGNRCDoQRaDDUAQ6
CEWgQ3AEOuJ3560FyBzfjaAQ34WgEt8EoBRfjaAYX4WgGh8dYHp8EYByfBGCenw0gOXxtwDA18fO
AAYwgAEMYAADGMAABjCAAQxgAA4h1nsA9Bds/SKEIDxOGaFoEMAShOgA0xGKp4hQPSWEpsEAQxGa
p4DQvcwIQxYAoPmGjQ5B4zMiTBsdhsZnQFg6OhYLj4YQYtuGn7d1/HVbRv/bltFejn0BBzpDHpDt
ugcAAAAASUVORK5CYII="""
_icon = tk.PhotoImage(data=_icon_data)
root.iconphoto(True, _icon)

style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame",          background=PRIMARY)
style.configure("TLabel",          background=PRIMARY, foreground=LABEL_FG,
                                   font=("Helvetica", 11, "bold"))
style.configure("TEntry",          fieldbackground=TEXT_BG, foreground=TEXT_FG,
                                   bordercolor="#aaccdd", insertcolor=PRIMARY)
style.configure("Accent.TButton",  background=PRIMARY, foreground=LABEL_FG,
                                   font=("Helvetica", 12, "bold"),
                                   borderwidth=0, relief="flat")
style.map("Accent.TButton",
          background=[("active", BTN_ACTIVE), ("pressed", BTN_ACTIVE)])

main_frame = ttk.Frame(root, padding="15")
main_frame.pack(fill=tk.BOTH, expand=True)

# 1. Curl Input Box
ttk.Label(main_frame, text="1. Paste Your Curl Command String:").pack(anchor=tk.W, pady=(0, 2))
text_curl = tk.Text(main_frame, height=6, font=("Courier", 10), wrap=tk.WORD,
                    borderwidth=0, relief="flat",
                    bg=TEXT_BG, fg=TEXT_FG,
                    insertbackground=PRIMARY,
                    selectbackground=PRIMARY, selectforeground=LABEL_FG)
text_curl.pack(fill=tk.X, pady=(0, 10))

default_curl = r'''curl ^"https://q-pmis2.tabadul.sa/api-gateway/tugspilot/boat/tugs-and-pilot-get-all-boats?page=0^&size=10^&search=^&_=1779192734934^" ^
  -H ^"Accept: application/json, text/javascript, */*; q=0.01^" ^
  -H ^"Accept-Language: en^" ^
  -H ^"Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJSMFU3LXVvTnowbThienVlQW1JMVRiYU5HeDNLdVpPWE43a2RncVpXWlQ0In0^" ^
  -H ^"Connection: keep-alive^" ^
  -H ^"Referer: https://q-pmis2.tabadul.sa/pilot-memo-activity/boat-master-listing^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36^" ^
  -H ^"X-Requested-With: XMLHttpRequest^"'''
text_curl.insert("1.0", default_curl)

# 2. Feature Class Name (auto-fills on paste)
ttk.Label(main_frame, text="2. Feature Class Name:").pack(anchor=tk.W, pady=(5, 2))
entry_custom_name = ttk.Entry(main_frame, font=("Helvetica", 11))
entry_custom_name.pack(fill=tk.X, pady=(0, 15))

def on_click_parse_name():
    curl_content = text_curl.get("1.0", tk.END).strip()
    predicted_pascal, _ = extract_feature_and_endpoint_from_url(curl_content)
    entry_custom_name.delete(0, tk.END)
    entry_custom_name.insert(0, predicted_pascal)

def on_curl_changed(event=None):
    on_click_parse_name()
    text_curl.edit_modified(False)

text_curl.bind("<<Modified>>", on_curl_changed)
on_click_parse_name()

# 3. Payload JSON Input Box
ttk.Label(main_frame, text="3. Paste JSON Output Data Payload Here:").pack(anchor=tk.W, pady=(0, 2))
text_json = tk.Text(main_frame, height=14, font=("Courier", 10), wrap=tk.WORD,
                    borderwidth=0, relief="flat",
                    bg=TEXT_BG, fg=TEXT_FG,
                    insertbackground=PRIMARY,
                    selectbackground=PRIMARY, selectforeground=LABEL_FG)
text_json.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

dummy_json = """{
    "responseCode": 200,
    "responseMessage": "SUCCESS",
    "data": {
        "content": [
            {
                "boatCode": "56211",
                "boatName": "AutoBoatname",
                "createdDate": "21-10-2025 15:57:54",
                "imoNo": 90336,
                "id": 100083,
                "status": null,
                "boatTypeRid": 2400,
                "boatClass": 2440,
                "portRid": 8,
                "boatTypeName": "Tugboat",
                "boatClassName": "Conventional tug",
                "ownType": "2402",
                "ownTypeCode": null,
                "ownTypeDesc": null,
                "typeOfBasisPurpose": 2446,
                "typeOfBasisPurposeDesc": null,
                "email": "aa@test.com",
                "contactNo": 654123456234,
                "startDate": null,
                "endDate": null,
                "buildYear": 2025,
                "buildType": 2455,
                "buildTypeDesc": null,
                "dimensions": null,
                "draft": 234,
                "capacity": null,
                "grt": 234,
                "topSpeed": 234,
                "safety": [{"id": 100099, "safetyEquipmentTypeRid": 2467, "safetyEquipmentExpiryDate": null, "safetyEquipmentTypeName": null}],
                "document": [{"id": 100072, "documentTypeRid": 1, "filePath": "1_1761051455.pdf", "documentValidityDate": "21-10-2025", "fileSizeKb": null, "fileType": null}],
                "createdBy": "portoperator"
            }
        ],
        "pageable": {
            "pageNumber": 0,
            "pageSize": 10,
            "sort": [],
            "offset": 0,
            "unpaged": false,
            "paged": true
        },
        "totalPages": 3,
        "totalElements": 26,
        "last": false,
        "size": 10,
        "number": 0,
        "sort": [],
        "numberOfElements": 10,
        "first": true,
        "empty": false
    }
}"""
text_json.insert("1.0", dummy_json)

def on_generate():
    process_generation(
        raw_feature_name=entry_custom_name.get(),
        raw_json=text_json.get("1.0", tk.END),
        raw_curl_str=text_curl.get("1.0", tk.END)
    )

btn_generate = ttk.Button(main_frame, text="🚀 Generate Data Architecture",
                           command=on_generate, style="Accent.TButton")
btn_generate.pack(fill=tk.X, ipady=12)

root.mainloop()

root.mainloop()