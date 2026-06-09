import re
import os
import json
from urllib.parse import urlparse, parse_qs
import tkinter as tk
from tkinter import messagebox, ttk


def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'[-_\s]+', '_', s2)

def clean_to_pascal(segment):
    # First split on camelCase/PascalCase boundaries, then on hyphens, underscores, spaces
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', segment)
    words = re.split(r'[-_\s/]', spaced)
    return "".join(w.lower().capitalize() for w in words if w)

def to_camel_case(text):
    pascal = clean_to_pascal(text)
    return pascal[0].lower() + pascal[1:]

def pascal_to_title(name):
    """Convert PascalCase to readable title: 'VesselTimestamp' -> 'Vessel Timestamp'"""
    words = re.sub(r'([A-Z])', r' \1', name).strip()
    return words

def extract_query_params_from_url(curl_str):
    """Extract query parameters from the URL in a curl command string."""
    if not curl_str:
        return {}
    url_match = re.search(r'(https?://[^\s\'"]+)', curl_str)
    if url_match:
        raw_url = url_match.group(1).replace('^', '')
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        # parse_qs returns lists, flatten single values
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    return {}


def extract_feature_and_endpoint_from_url(curl_str):
    if not curl_str:
        return "VesselTimeStamp", "https://qapigw.tabadul.sa/tabadul/pmis2/vesselvoyage/v2/vessel-time-stamp/pagination"
        
    url_match = re.search(r'(https?://[^\s\'"]+)', curl_str)
    if url_match:
        # Clean up windows line continuation carets (^) if present in the URL string
        raw_url = url_match.group(1).replace('^', '')
        full_url = raw_url.split('?')[0] 
        segments = [seg for seg in full_url.split('/') if seg and not seg.startswith('http')]
        
        if segments:
            # We add version tags here so they are cleanly popped off if they come after the feature name
            ignored_endpoints = ['pagination', 'crn', 'list', 'search', 'filter', 'v1', 'v2', 'v3', 'v4']
            while segments and segments[-1].lower() in ignored_endpoints:
                segments.pop()
            
            if segments:
                target_segment = segments[-1]
                # if last segment is a version token, fall back to previous
                if re.match(r'^v\d+$', target_segment.lower()) and len(segments) > 1:
                    target_segment = segments[-2]
                # If the last segment looks like a 'by-...' qualifier or an id placeholder, use the previous segment
                if re.match(r'^(by[-_].+|byid|by-id|by)$', target_segment.lower()) and len(segments) > 1:
                    target_segment = segments[-2]
                if re.search(r'\{.+\}', target_segment) and len(segments) > 1:
                    target_segment = segments[-2]
                # If target looks numeric, use previous segment
                if target_segment.isdigit() and len(segments) > 1:
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

def process_generation(raw_feature_name, raw_json, raw_curl_str, show_message=True, details_curl=None):
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
    query_params = extract_query_params_from_url(raw_curl_str)
    
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
    # Build query params string for the service template
    # -------------------------------------------------------------
    if query_params:
        params_lines = []
        method_params = []
        for key, value in query_params.items():
            if key == '_':
                continue  # Skip cache-busting timestamp param
            if key == 'page':
                method_params.append(f"    required int {key},")
                params_lines.append(f'      "{key}": {key}.toString(),')
            elif key == 'size':
                method_params.append(f"    int {key} = 10,")
                params_lines.append(f'      "{key}": {key}.toString(),')
            elif key == 'search':
                method_params.append(f"    String {key} = '',")
                params_lines.append(f'      "{key}": {key},')
            else:
                method_params.append(f"    String? {key},")
                params_lines.append(f'      if ({key} != null) "{key}": {key},')
        
        method_params_str = "\n".join(method_params)
        params_map_str = "\n".join(params_lines)
    else:
        method_params_str = "    required String crn,"
        params_map_str = '      "crn": crn,'

    # -------------------------------------------------------------
    service_template = f"""import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:multiple_result/multiple_result.dart';
import '../../../../constants/api_constants.dart';
import '../../../../constants/exceptions/exceptions.dart';
import '../../../../constants/network/network_handler.dart';
import '../models/__SNAKE_NAME___model.dart';

class __FEATURE_NAME__ManagementService {{
  Future<Result<__FEATURE_NAME__Response, AppException>> get__FEATURE_NAME__Details({{
{method_params_str}
    CancelToken? cancelToken,
  }}) async {{
    final params = {{
{params_map_str}
    }};

    try {{
      return await safeApiCall(() async {{
        final jsonResponse = await NetworkHandler.getRequest(
          headers: await NetworkHandler.getCommonHeaders(),
          endpoint: __ENDPOINT_VARIABLE__,
          params: params,
          cancelToken: cancelToken,
        );

        return Success(__FEATURE_NAME__ResponseMapper.fromMap(jsonResponse));
      }});
    }} catch (e) {{
      return Error(e as AppException);
    }}
  }}
}}

final __CAMEL_NAME__ServiceProvider = Provider.autoDispose<__FEATURE_NAME__ManagementService>((ref) {{
  return __FEATURE_NAME__ManagementService();
}});"""
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
          final searchQuery = ref.watch(searchQueryProvider);

          final result = await ref.watch(__CAMEL_NAME__ServiceProvider).get__FEATURE_NAME__Details(
            page: searchQuery.isNotEmpty ? 0 : page - 1,
            search: searchQuery,
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
        for k, v in content_obj.items():
            if k == "id": continue
            readable_label = k.replace('_', ' ').title()
            if isinstance(v, str) or v is None:
                dynamic_ui_fields += f"                        LabelValue(\n                            label: \"{readable_label}\",\n                            value: data.{k} ?? \"-\"),\n"
            else:
                dynamic_ui_fields += f"                        LabelValue(\n                            label: \"{readable_label}\",\n                            value: data.{k}?.toString() ?? \"-\"),\n"
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
        appBarTitle: "__LIST_TITLE__",
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
                            __FEATURE_NAME__DetailsRoute(__DETAILS_ROUTE_ARG__));
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
    list_title = pascal_to_title(feature_name)
    # When the details endpoint is crn-based, navigate with crn instead of id
    details_is_crn = 'crn' in extract_query_params_from_url(details_curl) if details_curl else False
    details_route_arg = 'crn: data.crn ?? ""' if details_is_crn else 'id: data.id ?? 0'
    view_code = view_template.replace("__FEATURE_NAME__", feature_name).replace("__SNAKE_NAME__", snake_name).replace("__CAMEL_NAME__", camel_name).replace("__UI_DYNAMIC_FIELDS__", dynamic_ui_fields).replace("__LIST_TITLE__", list_title).replace("__DETAILS_ROUTE_ARG__", details_route_arg)

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
        
        if show_message:
            messagebox.showinfo("Success", f"🎉 Complete Directory Architecture Created On Desktop!\n\n"
                                           f"Folder: Desktop/{snake_name}/\n"
                                           f"├── models/{snake_name}_model.dart\n"
                                           f"├── services/{snake_name}_service.dart\n"
                                           f"├── notifiers/{snake_name}_notifier.dart\n"
                                           f"└── views/{snake_name}_list_view.dart")
    except Exception as e:
        messagebox.showerror("File Error", f"Could not create folder architecture:\n{str(e)}")


# -------------------------------------------------------------
# DETAILS MODEL CODE GENERATOR
# -------------------------------------------------------------
def generate_details_model_code(feature_name, snake_name, camel_name, details_data):
    data_obj = details_data.get("data", {})
    if not isinstance(data_obj, dict):
        data_obj = {}

    model_code = f"import 'package:dart_mappable/dart_mappable.dart';\n\n"
    model_code += f"part '{snake_name}_details_model.mapper.dart';\n\n"

    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}DetailsResponse with {feature_name}DetailsResponseMappable {{\n"
    model_code += "  final int responseCode;\n  final String responseMessage;\n\n"
    model_code += f"  @MappableField(key: \"data\")\n  final {feature_name}Details? {camel_name}Details;\n\n"
    model_code += f"  {feature_name}DetailsResponse({{\n    required this.responseCode,\n    required this.responseMessage,\n    this.{camel_name}Details,\n  }});\n}}\n\n"

    model_code += f"@MappableClass(ignoreNull: true)\nclass {feature_name}Details with {feature_name}DetailsMappable {{\n"
    if data_obj:
        for k, v in data_obj.items():
            if isinstance(v, list):
                model_code += f"  final List<dynamic>? {k};\n"
            elif isinstance(v, dict):
                model_code += f"  final dynamic {k};\n"
            else:
                model_code += f"  final {get_dart_type(v, k, feature_name)} {k};\n"
        model_code += f"\n  {feature_name}Details({{\n"
        for k in data_obj.keys():
            model_code += f"    this.{k},\n"
        model_code += "  });\n}"
    else:
        model_code += "  final int? id;\n\n"
        model_code += f"  {feature_name}Details({{\n    this.id,\n  }});\n}}"

    return model_code


# -------------------------------------------------------------
# COMBINED SERVICE CODE GENERATOR (list + details)
# -------------------------------------------------------------
def generate_combined_service_code(feature_name, snake_name, camel_name, list_url, details_url, list_curl=None, details_curl=None):
    list_query_params = extract_query_params_from_url(list_curl) if list_curl else {}

    if list_query_params:
        list_method_params_lines = []
        list_params_map_lines = []
        for key, value in list_query_params.items():
            if key == '_':
                continue
            if key == 'page':
                list_method_params_lines.append(f"    required int {key},")
                list_params_map_lines.append(f'      "{key}": {key}.toString(),')
            elif key == 'size':
                list_method_params_lines.append(f"    int {key} = 10,")
                list_params_map_lines.append(f'      "{key}": {key}.toString(),')
            elif key == 'search':
                list_method_params_lines.append(f"    String {key} = '',")
                list_params_map_lines.append(f'      "{key}": {key},')
            else:
                list_method_params_lines.append(f"    String? {key},")
                list_params_map_lines.append(f'      if ({key} != null) "{key}": {key},')
        list_method_params_str = "\n".join(list_method_params_lines)
        list_params_map_str = "\n".join(list_params_map_lines)
    else:
        list_method_params_str = "    required String crn,"
        list_params_map_str = '      "crn": crn,'

    details_query_params = extract_query_params_from_url(details_curl) if details_curl else {}
    if details_query_params:
        details_method_params_lines = []
        details_params_map_lines = []
        for key, value in details_query_params.items():
            if key == '_':
                continue
            if key == 'page':
                details_method_params_lines.append(f"    required int {key},")
                details_params_map_lines.append(f'      "{key}": {key}.toString(),')
            elif key == 'size':
                details_method_params_lines.append(f"    int {key} = 10,")
                details_params_map_lines.append(f'      "{key}": {key}.toString(),')
            else:
                # treat details params as required strings (e.g., crn)
                details_method_params_lines.append(f"    required String {key},")
                details_params_map_lines.append(f'      "{key}": {key},')
        details_method_params_str = "\n".join(details_method_params_lines)
        details_params_map_str = "\n".join(details_params_map_lines)

        details_method_block = f"""  Future<Result<{feature_name}DetailsResponse, AppException>> get{feature_name}ById({{
{details_method_params_str}
    CancelToken? cancelToken,
  }}) async {{
    final params = {{
{details_params_map_str}
    }};
    try {{
      return await safeApiCall(() async {{
        final jsonResponse = await NetworkHandler.getRequest(
          headers: await NetworkHandler.getCommonHeaders(),
          endpoint: '{details_url}',
          params: params,
          cancelToken: cancelToken,
        );
        return Success({feature_name}DetailsResponseMapper.fromMap(jsonResponse));
      }});
    }} catch (e) {{
      return Error(e as AppException);
    }}
  }}\n\n"""
    else:
        details_method_block = f"""  Future<Result<{feature_name}DetailsResponse, AppException>> get{feature_name}ById({{
    required int id,
    CancelToken? cancelToken,
  }}) async {{
    try {{
      return await safeApiCall(() async {{
        final jsonResponse = await NetworkHandler.getRequest(
          headers: await NetworkHandler.getCommonHeaders(),
          endpoint: '{details_url}/$id',
          cancelToken: cancelToken,
        );
        return Success({feature_name}DetailsResponseMapper.fromMap(jsonResponse));
      }});
    }} catch (e) {{
      return Error(e as AppException);
    }}
  }}\n\n"""

    return f"""import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:multiple_result/multiple_result.dart';
import '../../../../constants/api_constants.dart';
import '../../../../constants/exceptions/exceptions.dart';
import '../../../../constants/network/network_handler.dart';
import '../models/{snake_name}_model.dart';
import '../models/{snake_name}_details_model.dart';

class {feature_name}ManagementService {{
  Future<Result<{feature_name}Response, AppException>> get{feature_name}Details({{
{list_method_params_str}
    CancelToken? cancelToken,
  }}) async {{
    final params = {{
{list_params_map_str}
    }};
    try {{
      return await safeApiCall(() async {{
        final jsonResponse = await NetworkHandler.getRequest(
          headers: await NetworkHandler.getCommonHeaders(),
          endpoint: '{list_url}',
          params: params,
          cancelToken: cancelToken,
        );
        return Success({feature_name}ResponseMapper.fromMap(jsonResponse));
      }});
    }} catch (e) {{
      return Error(e as AppException);
    }}
  }}

{details_method_block}}}

final {camel_name}ServiceProvider = Provider.autoDispose<{feature_name}ManagementService>((ref) {{
  return {feature_name}ManagementService();
}});"""


# -------------------------------------------------------------
# DETAILS NOTIFIER CODE GENERATOR
# -------------------------------------------------------------
def generate_details_notifier_code(feature_name, snake_name, camel_name, details_curl=None):
    details_query_params = extract_query_params_from_url(details_curl) if details_curl else {}
    # If details endpoint expects a 'crn' query param, generate notifier that accepts String parameter
    if 'crn' in details_query_params:
        return f"""import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mawani_pmis/utils/extension/cancel_extension.dart';
import 'package:mawani_pmis/utils/extension/result_extension.dart';
import '../models/{snake_name}_details_model.dart';
import '../services/{snake_name}_service.dart';

class {feature_name}DetailsViewNotifier extends AutoDisposeFamilyAsyncNotifier<{feature_name}Details?, String> {{

  @override
  FutureOr<{feature_name}Details?> build(String id) async {{
    state = const AsyncLoading();
    try {{
      final result = await ref.watch({camel_name}ServiceProvider).get{feature_name}ById(
        crn: id,
        cancelToken: ref.cancelToken(),
      );

      final response = result.getOrThrowError();
      return response.{camel_name}Details;
    }} catch (e) {{
      state = AsyncError(e, StackTrace.current);
      return null;
    }}
  }}
}}

final {camel_name}DetailsNotifierProvider = AsyncNotifierProvider.autoDispose
    .family<{feature_name}DetailsViewNotifier, {feature_name}Details?, String>(
  {feature_name}DetailsViewNotifier.new,
  name: "{feature_name}DetailsNotifier",
);"""
    else:
        return f"""import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mawani_pmis/utils/extension/cancel_extension.dart';
import 'package:mawani_pmis/utils/extension/result_extension.dart';
import '../models/{snake_name}_details_model.dart';
import '../services/{snake_name}_service.dart';

class {feature_name}DetailsViewNotifier extends AutoDisposeFamilyAsyncNotifier<{feature_name}Details?, int> {{

  @override
  FutureOr<{feature_name}Details?> build(int id) async {{
    state = const AsyncLoading();
    try {{
      final result = await ref.watch({camel_name}ServiceProvider).get{feature_name}ById(
        id: id,
        cancelToken: ref.cancelToken(),
      );

      final response = result.getOrThrowError();
      return response.{camel_name}Details;
    }} catch (e) {{
      state = AsyncError(e, StackTrace.current);
      return null;
    }}
  }}
}}

final {camel_name}DetailsNotifierProvider = AsyncNotifierProvider.autoDispose
    .family<{feature_name}DetailsViewNotifier, {feature_name}Details?, int>(
  {feature_name}DetailsViewNotifier.new,
  name: "{feature_name}DetailsNotifier",
);"""

# -------------------------------------------------------------
# DETAILS VIEW CODE GENERATOR
# -------------------------------------------------------------
def generate_details_view_code(feature_name, snake_name, camel_name, details_data, details_curl=None):
    data_obj = details_data.get("data", {})
    if not isinstance(data_obj, dict):
        data_obj = {}

    list_title = pascal_to_title(feature_name)

    # Generate TitleSubtitleModel fields
    detail_fields = ""
    if data_obj:
        for k, v in data_obj.items():
            if k == "id":
                continue
            readable_label = k.replace('_', ' ').title()
            if isinstance(v, str) or v is None:
                detail_fields += f"                      TitleSubtitleModel(\n                        title: \"{readable_label}\",\n                        subTitle: data.{k} ?? \"-\",\n                      ),\n"
            else:
                detail_fields += f"                      TitleSubtitleModel(\n                        title: \"{readable_label}\",\n                        subTitle: data.{k}?.toString() ?? \"-\",\n                      ),\n"
    else:
        detail_fields = f"                      TitleSubtitleModel(\n                        title: \"Id\",\n                        subTitle: data.id?.toString() ?? \"-\",\n                      ),\n"

    details_query = extract_query_params_from_url(details_curl) if details_curl else {}
    is_crn = "crn" in details_query
    id_type = "String" if is_crn else "int"
    param_name = "crn" if is_crn else "id"

    return f"""import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mawani_pmis/constants/app_sizes.dart';
import 'package:mawani_pmis/features/common/widgets/common_app_bar.dart';
import 'package:mawani_pmis/features/common/widgets/common_background.dart';
import 'package:mawani_pmis/features/common/models/title_subtile_model.dart';
import 'package:mawani_pmis/features/common/widgets/custom_expansion_tile_with_details.dart';
import '../../../common/widgets/common_circular_progress.dart';
import '../../../common/widgets/common_error_widget.dart';
import '../../../common/widgets/common_no_data_widget.dart';
import '../notifiers/{snake_name}_details_notifier.dart';

@RoutePage()
class {feature_name}DetailsView extends ConsumerWidget {{
  final {id_type} {param_name};

  const {feature_name}DetailsView({{super.key, required this.{param_name}}});

  @override
  Widget build(BuildContext context, WidgetRef ref) {{
    final detailsAsync = ref.watch({camel_name}DetailsNotifierProvider({param_name}));

    return CommonBackground(
      appBar: const CommonAppBar(appBarTitle: "{list_title} Details"),
      body: detailsAsync.when(
        data: (data) {{
          if (data == null) {{
            return const Center(child: CommonNoDataWidget());
          }}
          return Padding(
            padding: AppSizes.symmetricHorizontalMargin,
            child: SingleChildScrollView(
              child: Column(
                children: [
                  CustomExpansionTileWithDetails(
                    initiallyExpanded: true,
                    heading: "{list_title} Details",
                    titleSubTitles: [
{detail_fields}                    ],
                  ),
                ],
              ),
            ),
          );
        }},
        error: (error, stack) {{
          return CommonErrorWidget(
            error,
            reload: () => ref.invalidate({camel_name}DetailsNotifierProvider({param_name})),
          );
        }},
        loading: () => CommonCircularProgress(),
      ),
    );
  }}
}}"""

# -------------------------------------------------------------
# COMBINED GENERATION (list + details)
# -------------------------------------------------------------
def process_combined_generation(list_name, list_json_str, list_curl, details_json_str, details_curl):
    list_name = list_name.strip()
    if not list_name:
        messagebox.showerror("Error", "List Feature Name cannot be empty.")
        return

    try:
        details_data = json.loads(details_json_str.strip())
    except Exception as e:
        messagebox.showerror("JSON Error", f"Invalid Details JSON:\n{str(e)}")
        return

    # Generate list files first (reuses existing logic)
    process_generation(list_name, list_json_str, list_curl, show_message=False, details_curl=details_curl)

    # Derive naming from list name
    feature_name = clean_to_pascal(list_name)
    snake_name   = camel_to_snake(list_name)
    camel_name   = to_camel_case(list_name)

    _, list_url    = extract_feature_and_endpoint_from_url(list_curl)
    _, details_url = extract_feature_and_endpoint_from_url(details_curl)

    desktop_dir       = os.path.expanduser("~/Desktop")
    feature_root_dir  = os.path.join(desktop_dir, snake_name)
    models_dir        = os.path.join(feature_root_dir, "models")
    services_dir      = os.path.join(feature_root_dir, "services")
    notifiers_dir     = os.path.join(feature_root_dir, "notifiers")
    views_dir         = os.path.join(feature_root_dir, "views")

    try:
        details_model_code    = generate_details_model_code(feature_name, snake_name, camel_name, details_data)
        combined_service_code = generate_combined_service_code(feature_name, snake_name, camel_name, list_url, details_url, list_curl=list_curl, details_curl=details_curl)
        details_notifier_code = generate_details_notifier_code(feature_name, snake_name, camel_name, details_curl=details_curl)
        details_view_code     = generate_details_view_code(feature_name, snake_name, camel_name, details_data, details_curl=details_curl)

        with open(os.path.join(models_dir,    f"{snake_name}_details_model.dart"), "w") as f:
            f.write(details_model_code)
        with open(os.path.join(services_dir,  f"{snake_name}_service.dart"), "w") as f:
            f.write(combined_service_code)
        with open(os.path.join(notifiers_dir, f"{snake_name}_details_notifier.dart"), "w") as f:
            f.write(details_notifier_code)
        with open(os.path.join(views_dir,     f"{snake_name}_details_view.dart"), "w") as f:
            f.write(details_view_code)

        messagebox.showinfo("Success",
            f"🎉 Full Architecture (List + Details) Created!\n\n"
            f"Folder: Desktop/{snake_name}/\n"
            f"├── models/{snake_name}_model.dart\n"
            f"├── models/{snake_name}_details_model.dart\n"
            f"├── services/{snake_name}_service.dart  ← combined\n"
            f"├── notifiers/{snake_name}_notifier.dart\n"
            f"├── notifiers/{snake_name}_details_notifier.dart\n"
            f"├── views/{snake_name}_list_view.dart\n"
            f"└── views/{snake_name}_details_view.dart")
    except Exception as e:
        messagebox.showerror("File Error", f"Could not create files:\n{str(e)}")


root = tk.Tk()
root.title("Structured Curl Architecture Folder Generator")
root.geometry("860x940")

# ── Light corporate palette ─────────────────────────
PRIMARY    = "#1E3A8A"   # Deep Corporate Navy Blue
ACCENT     = "#3B82F6"   # Vibrant Blue (active states)
SECONDARY  = "#F59E0B"   # Solar Orange (alternate accent)
BG         = "#F8FAFC"   # Off-White form background
TEXT_BG    = "#FFFFFF"   # Input background
TEXT_FG    = "#0F172A"   # Dark slate text
LABEL_FG   = "#0F172A"   # Label color
BTN_ACTIVE = "#3B82F6"   # Button hover (vibrant blue)
BORDER     = "#E2E8F0"   # Light gray border
# ───────────────────────────────────────────────────

root.configure(bg=BG)

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

style.configure("TFrame",
                background=BG)
style.configure("Card.TFrame",
                background="#FFFFFF", relief="flat")
style.configure("TLabel",
                background=BG, foreground=LABEL_FG,
                font=("Helvetica", 11))
style.configure("Heading.TLabel",
                background=BG, foreground=PRIMARY,
                font=("Helvetica", 13, "bold"))
style.configure("TEntry",
                fieldbackground=TEXT_BG, foreground=TEXT_FG,
                bordercolor=BORDER, insertcolor=ACCENT,
                padding=10)
style.configure("TCombobox",
                fieldbackground=TEXT_BG, foreground=TEXT_FG,
                padding=8)

# Action button (primary CTA)
style.configure("Accent.TButton",
                background=PRIMARY, foreground="#ffffff",
                font=("Helvetica", 12, "bold"),
                borderwidth=0, relief="flat",
                padding=8)
style.map("Accent.TButton",
          background=[("active", BTN_ACTIVE), ("pressed", ACCENT)],
          foreground=[("disabled", "#94a3b8")])

# Notebook chrome
style.configure("TNotebook",
                background=BG, borderwidth=0, tabmargins=[8, 8, 0, 0])
style.configure("TNotebook.Tab",
                background=BG, foreground=LABEL_FG,
                font=("Helvetica", 10),
                padding=[10, 6])
style.map("TNotebook.Tab",
          background=[("selected", BG)],
          foreground=[("selected", PRIMARY)],
          font=[("selected", ("Helvetica", 12, "bold")), ("!selected", ("Helvetica", 10))],
          padding=[("selected", [12, 8]), ("!selected", [10, 6])])

style.configure("Separator.TSeparator", background=BORDER)

# Title bar canvas strip
header = tk.Canvas(root, bg="#11111b", height=56, highlightthickness=0)
header.pack(fill=tk.X)
header.create_text(20, 28, text="⚡ Curl → Riverpod Architecture Generator",
                   fill=ACCENT, font=("Helvetica", 15, "bold"), anchor="w")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(4, 14))


# ── Helper to build a tab's fields (no button — caller adds it) ────────────
def build_tab(parent, default_curl_text, default_json_text):
    frame = ttk.Frame(parent, padding="18")

    # 1. Curl
    ttk.Label(frame, text="1. Paste Your Curl Command String:").pack(anchor=tk.W, pady=(0, 3))
    text_curl = tk.Text(frame, height=6, font=("Courier", 10), wrap=tk.WORD,
                        borderwidth=1, relief="solid",
                        bg=TEXT_BG, fg=TEXT_FG,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT,
                        insertbackground=ACCENT,
                        selectbackground=PRIMARY, selectforeground="#ffffff")
    text_curl.pack(fill=tk.X, pady=(0, 12))
    text_curl.insert("1.0", default_curl_text)

    # 2. Feature Class Name (auto-fills on paste)
    ttk.Label(frame, text="2. Feature Class Name:").pack(anchor=tk.W, pady=(5, 3))
    entry_name = ttk.Entry(frame, font=("Helvetica", 11))
    entry_name.pack(fill=tk.X, pady=(0, 16))

    def parse_name():
        pascal, _ = extract_feature_and_endpoint_from_url(text_curl.get("1.0", tk.END).strip())
        entry_name.delete(0, tk.END)
        entry_name.insert(0, pascal)

    def on_curl_modified(event=None):
        parse_name()
        text_curl.edit_modified(False)

    text_curl.bind("<<Modified>>", on_curl_modified)
    parse_name()

    # 3. JSON Payload
    ttk.Label(frame, text="3. Paste JSON Output Data Payload Here:").pack(anchor=tk.W, pady=(0, 3))
    text_json = tk.Text(frame, height=14, font=("Courier", 10), wrap=tk.WORD,
                        borderwidth=1, relief="solid",
                        bg=TEXT_BG, fg=TEXT_FG,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT,
                        insertbackground=ACCENT,
                        selectbackground=PRIMARY, selectforeground="#ffffff")
    text_json.pack(fill=tk.BOTH, expand=True, pady=(0, 16))
    text_json.insert("1.0", default_json_text)

    def get_data():
        return entry_name.get(), text_json.get("1.0", tk.END), text_curl.get("1.0", tk.END)

    return frame, get_data


def create_card(parent, title=None):
    """Create a white card with a subtle border to group fields."""
    outer = tk.Frame(parent, bg=BORDER)
    inner = tk.Frame(outer, bg=TEXT_BG, padx=12, pady=12)
    outer.pack(fill=tk.X, pady=(8, 12))
    inner.pack(fill=tk.BOTH, expand=True)
    return inner


def build_data_entry_form(parent):
    """Create a modern, card-based data entry form."""
    frame = ttk.Frame(parent, padding=18)

    # User Information
    user_card = create_card(frame)
    user_card.grid_columnconfigure(0, weight=0)
    user_card.grid_columnconfigure(1, weight=1)
    ttk.Label(user_card, text="User Information", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    fields = [("First name", ""), ("Last name", ""), ("Email", ""), ("Phone", "")]
    for i, (label_text, _) in enumerate(fields):
        row = i + 1
        ttk.Label(user_card, text=label_text).grid(row=row, column=0, sticky="w", pady=8)
        ent = ttk.Entry(user_card)
        ent.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=8)

    # Registration Status
    status_card = create_card(frame)
    status_card.grid_columnconfigure(1, weight=1)
    ttk.Label(status_card, text="Registration Status", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Label(status_card, text="Status").grid(row=1, column=0, sticky="w", pady=8)
    status_cb = ttk.Combobox(status_card, values=["Active", "Pending", "Inactive"], state="readonly")
    status_cb.current(0)
    status_cb.grid(row=1, column=1, sticky="ew", padx=(12, 0))

    ttk.Label(status_card, text="Priority").grid(row=2, column=0, sticky="w", pady=8)
    spin = tk.Spinbox(status_card, from_=1, to=10, bd=0, relief="flat")
    spin.grid(row=2, column=1, sticky="w", padx=(12, 0))

    # Terms & Conditions
    terms_card = create_card(frame)
    ttk.Label(terms_card, text="Terms & Conditions", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    chk_var = tk.IntVar()
    ttk.Checkbutton(terms_card, text="I agree to the terms and privacy policy", variable=chk_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=8)

    # Action
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(12, 0))
    ttk.Button(btn_frame, text="Enter Data", style="Accent.TButton",
               command=lambda: messagebox.showinfo("Saved", "Data entered successfully")).pack(side=tk.RIGHT, ipady=8)

    return frame


# ── Tab 1 — List API ────────────────────────────────────────────────────────
default_curl_list = r'''curl ^"https://qapigw.tabadul.sa/tabadul/pmis2/vesselcargo/bay-plan/v2/bay-plans?page=0^&size=10^&search=^&_=1781014505090^" ^
  -H ^"Accept: application/json, text/javascript, */*; q=0.01^" ^
  -H ^"Accept-Language: en^" ^
  -H ^"Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJSMFU3LXVvTnowbThienVlQW1JMVRiYU5HeDNLdVpPWE43a2RncVpXWlQ0In0.eyJleHAiOjE3ODEwMTYzMDUsImlhdCI6MTc4MTAxNDUwNSwiYXV0aF90aW1lIjoxNzgxMDE0NTA0LCJqdGkiOiIzOWQzMmZlYy1iNGJkLTQ3MzUtYmQyNC00Y2JmM2Y4YzdiMDMiLCJpc3MiOiJodHRwczovL3EtcG1pczIudGFiYWR1bC5zYS9hdXRoL3JlYWxtcy9QTUlTIiwiYXVkIjpbInJlYWxtLW1hbmFnZW1lbnQiLCJhY2NvdW50Il0sInN1YiI6IjkzMjM2NWU0LTI5NDEtNDI2NC04MjEyLTM4ZTgyMzQzMTU2NiIsInR5cCI6IkJlYXJlciIsImF6cCI6IlBNSVNfY2xpZW50Iiwibm9uY2UiOiJjN2NkMDI2YS01NDAwLTRkNTEtYmI4Yy05OWEyYTkxMjkwNmMiLCJzZXNzaW9uX3N0YXRlIjoiMWQxYzAzYTItMWM2MC00MzdiLWE3NDYtYzhkNjc2NzVkYzkwIiwiYWxsb3dlZC1vcmlnaW5zIjpbImh0dHBzOi8vcS1wbWlzMi50YWJhZHVsLnNhIiwiaHR0cHM6Ly91LXBtaXMudGFiYWR1bC5zYSJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsicG1pc3VzZXIiLCJQT0FETSIsIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1wbWlzIiwidW1hX2F1dGhvcml6YXRpb24iLCJQTyJdfSwicmVzb3VyY2VfYWNjZXNzIjp7InJlYWxtLW1hbmFnZW1lbnQiOnsicm9sZXMiOlsibWFuYWdlLXVzZXJzIiwidmlldy11c2VycyIsInF1ZXJ5LWdyb3VwcyIsInF1ZXJ5LXVzZXJzIl19LCJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIHBtaXN1c2VyIiwic2lkIjoiMWQxYzAzYTItMWM2MC00MzdiLWE3NDYtYzhkNjc2NzVkYzkwIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJkYW0wMDEiLCJsb2NhbGUiOiJlbiIsImVtYWlsIjoidGVzdEB0ZXN0LnNhIn0.u2IguGI3mjRutVFF2AsEK2M2U28FlxCQN85505Gu5xgToxaDLtX4dCQ_AZ7oYx8YrntE1Ig-VoX2h0XlLXqDwOikUpzijYPzvL8NRPn-XmrrFrFLhAlYx8bIYudmg1kkLSYW1YTp0gMjif74HfirqyCE4p_gAUK8b073QLjTzrgFEZLt0mRkiM9JJFudaSQZELW8kQxJjvozB7YWPhZriS8JbqOgPsnDkfdFh0GUlyZSAW6HWpkhweKhZIcbwkD4OC2qLnlsUKYMEcRGcMOGZfbWGDFWK8XBNT9pJvo_qgrUXKjEmRWhX49LUYPzHdYH7tOiJg2TYNibktmBNQI14w^" ^
  -H ^"Connection: keep-alive^" ^
  -H ^"Origin: https://q-pmis2.tabadul.sa^" ^
  -H ^"Referer: https://q-pmis2.tabadul.sa/^" ^
  -H ^"Sec-Fetch-Dest: empty^" ^
  -H ^"Sec-Fetch-Mode: cors^" ^
  -H ^"Sec-Fetch-Site: same-site^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36^" ^
  -H ^"sec-ch-ua: ^\^"Chromium^\^";v=^\^"148^\^", ^\^"Google Chrome^\^";v=^\^"148^\^", ^\^"Not/A)Brand^\^";v=^\^"99^\^"^" ^
  -H ^"sec-ch-ua-mobile: ?0^" ^
  -H ^"sec-ch-ua-platform: ^\^"Windows^\^"^"'''

default_json_list = """{
    "responseCode": 200,
    "responseMessage": "SUCCESS",
    "data": {
        "content": [
            {
                "crn": "20250507000112",
                "vcn": "DAM0000914",
                "vesselName": "vesselName English",
                "imoNo": "8579298",
                "createdDate": "07-05-2025",
                "approvalStatusRid": "Submitted",
                "updatedDate": "07-05-2025 14:21:07"
            }
        ],
        "pageable": {
            "pageNumber": 0,
            "pageSize": 10,
            "sort": [
                {
                    "direction": "DESC",
                    "property": "updatedDate",
                    "ignoreCase": false,
                    "nullHandling": "NATIVE",
                    "ascending": false,
                    "descending": true
                }
            ],
            "offset": 0,
            "paged": true,
            "unpaged": false
        },
        "last": true,
        "totalElements": 1,
        "totalPages": 1,
        "size": 10,
        "number": 0,
        "sort": [
            {
                "direction": "DESC",
                "property": "updatedDate",
                "ignoreCase": false,
                "nullHandling": "NATIVE",
                "ascending": false,
                "descending": true
            }
        ],
        "first": true,
        "numberOfElements": 1,
        "empty": false
    }
}"""

tab1_frame, get_list_data = build_tab(notebook, default_curl_list, default_json_list)

def on_list_generate():
    name, json_str, curl = get_list_data()
    process_generation(raw_feature_name=name, raw_json=json_str, raw_curl_str=curl)

ttk.Button(tab1_frame, text=" Generate List Architecture",
           command=on_list_generate, style="Accent.TButton").pack(fill=tk.X, ipady=12)
notebook.add(tab1_frame, text="  📋 List API  ")


# ── Tab 2 — Details API ─────────────────────────────────────────────────────
default_curl_details = r'''curl ^"https://qapigw.tabadul.sa/tabadul/pmis2/vesselcargo/bay-plan/bay-plan-crn?crn=20250507000112^" ^
  -H ^"Accept: application/json, text/plain, */*^" ^
  -H ^"Accept-Language: en^" ^
  -H ^"Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJSMFU3LXVvTnowbThienVlQW1JMVRiYU5HeDNLdVpPWE43a2RncVpXWlQ0In0.eyJleHAiOjE3ODEwMTYzMDUsImlhdCI6MTc4MTAxNDUwNSwiYXV0aF90aW1lIjoxNzgxMDE0NTA0LCJqdGkiOiIzOWQzMmZlYy1iNGJkLTQ3MzUtYmQyNC00Y2JmM2Y4YzdiMDMiLCJpc3MiOiJodHRwczovL3EtcG1pczIudGFiYWR1bC5zYS9hdXRoL3JlYWxtcy9QTUlTIiwiYXVkIjpbInJlYWxtLW1hbmFnZW1lbnQiLCJhY2NvdW50Il0sInN1YiI6IjkzMjM2NWU0LTI5NDEtNDI2NC04MjEyLTM4ZTgyMzQzMTU2NiIsInR5cCI6IkJlYXJlciIsImF6cCI6IlBNSVNfY2xpZW50Iiwibm9uY2UiOiJjN2NkMDI2YS01NDAwLTRkNTEtYmI4Yy05OWEyYTkxMjkwNmMiLCJzZXNzaW9uX3N0YXRlIjoiMWQxYzAzYTItMWM2MC00MzdiLWE3NDYtYzhkNjc2NzVkYzkwIiwiYWxsb3dlZC1vcmlnaW5zIjpbImh0dHBzOi8vcS1wbWlzMi50YWJhZHVsLnNhIiwiaHR0cHM6Ly91LXBtaXMudGFiYWR1bC5zYSJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsicG1pc3VzZXIiLCJQT0FETSIsIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1wbWlzIiwidW1hX2F1dGhvcml6YXRpb24iLCJQTyJdfSwicmVzb3VyY2VfYWNjZXNzIjp7InJlYWxtLW1hbmFnZW1lbnQiOnsicm9sZXMiOlsibWFuYWdlLXVzZXJzIiwidmlldy11c2VycyIsInF1ZXJ5LWdyb3VwcyIsInF1ZXJ5LXVzZXJzIl19LCJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIHBtaXN1c2VyIiwic2lkIjoiMWQxYzAzYTItMWM2MC00MzdiLWE3NDYtYzhkNjc2NzVkYzkwIiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJkYW0wMDEiLCJsb2NhbGUiOiJlbiIsImVtYWlsIjoidGVzdEB0ZXN0LnNhIn0.u2IguGI3mjRutVFF2AsEK2M2U28FlxCQN85505Gu5xgToxaDLtX4dCQ_AZ7oYx8YrntE1Ig-VoX2h0XlLXqDwOikUpzijYPzvL8NRPn-XmrrFrFLhAlYx8bIYudmg1kkLSYW1YTp0gMjif74HfirqyCE4p_gAUK8b073QLjTzrgFEZLt0mRkiM9JJFudaSQZELW8kQxJjvozB7YWPhZriS8JbqOgPsnDkfdFh0GUlyZSAW6HWpkhweKhZIcbwkD4OC2qLnlsUKYMEcRGcMOGZfbWGDFWK8XBNT9pJvo_qgrUXKjEmRWhX49LUYPzHdYH7tOiJg2TYNibktmBNQI14w^" ^
  -H ^"Connection: keep-alive^" ^
  -H ^"Content-Type: text^" ^
  -H ^"Origin: https://q-pmis2.tabadul.sa^" ^
  -H ^"Referer: https://q-pmis2.tabadul.sa/^" ^
  -H ^"Sec-Fetch-Dest: empty^" ^
  -H ^"Sec-Fetch-Mode: cors^" ^
  -H ^"Sec-Fetch-Site: same-site^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36^" ^
  -H ^"sec-ch-ua: ^\^"Chromium^\^";v=^\^"148^\^", ^\^"Google Chrome^\^";v=^\^"148^\^", ^\^"Not/A)Brand^\^";v=^\^"99^\^"^" ^
  -H ^"sec-ch-ua-mobile: ?0^" ^
  -H ^"sec-ch-ua-platform: ^\^"Windows^\^"^"'''

default_json_details = """{
    "responseCode": 200,
    "responseMessage": "SUCCESS",
    "data": {
        "id": 100009,
        "voyageRid": 121793,
        "crn": 20250507000112,
        "filePath": null,
        "approvalStatusRid": 1,
        "branchId": "lizj",
        "orgId": "nwze0001",
        "portId": 8,
        "vcn": "DAM0000914",
        "vesselName": "vesselName English",
        "imoNo": "8579298",
        "callSign": "1234567",
        "voyageNo": "12",
        "status": "Submitted",
        "totalContainer": 19,
        "containers": []
    }
}"""

tab2_frame, get_details_data = build_tab(notebook, default_curl_details, default_json_details)

def on_combined_generate():
    list_name, list_json, list_curl   = get_list_data()
    _,         det_json,  det_curl    = get_details_data()
    process_combined_generation(list_name, list_json, list_curl, det_json, det_curl)

ttk.Button(tab2_frame, text=" Generate List + Details Architecture",
           command=on_combined_generate, style="Accent.TButton").pack(fill=tk.X, ipady=12)
notebook.add(tab2_frame, text="  🔍 Details API  ")

root.mainloop()