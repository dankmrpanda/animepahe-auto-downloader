/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ 9028:
/***/ ((module, __webpack_exports__, __webpack_require__) => {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   A: () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(5516);
/* harmony import */ var _node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(1364);
/* harmony import */ var _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(_node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var _node_modules_css_loader_dist_cjs_js_ruleSet_1_rules_1_use_1_theme_ui_light_css__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(4341);
// Imports



var ___CSS_LOADER_EXPORT___ = _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1___default()((_node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0___default()));
___CSS_LOADER_EXPORT___.i(_node_modules_css_loader_dist_cjs_js_ruleSet_1_rules_1_use_1_theme_ui_light_css__WEBPACK_IMPORTED_MODULE_2__/* ["default"] */ .A);
// Module
___CSS_LOADER_EXPORT___.push([module.id, `/*
 * This file is part of Adblock Plus <https://adblockplus.org/>,
 * Copyright (C) 2006-present eyeo GmbH
 *
 * Adblock Plus is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Adblock Plus is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.
 */

* {
  box-sizing: border-box;
  font-family: "Lucida Grande", "Segoe UI", Ubuntu, Tahoma, Arial, sans-serif;
  font-size: 11px;
}

html {
  overflow: hidden;
  height: 100%;
}

a {
  color: inherit;
}

body {
  display: flex;
  flex-direction: column;
  height: 100%;
  margin: 0;
  color: #303942;
}

body.default {
  background-color: var(--background-color-primary);
}

body.dark {
  color: #fff;
}

table {
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
}

table * {
  overflow: hidden;
  text-overflow: ellipsis;
}

td {
  padding: 3px;
  border-left: 1px solid #cdcdcd;
  white-space: nowrap;
}

td:first-child {
  border-left-style: none;
}

col:nth-child(2) {
  width: 115px;
}

col:nth-child(3) {
  width: 50%;
}

header {
  overflow-y: scroll;
  border-bottom: 1px solid #cdcdcd;
  flex-shrink: 0;
}

/*
 * We have to add a scrollbar to the header to have the columns there aligned
 * with the table below. But we don't want the scrollbar to be visible there.
 */
header::-webkit-scrollbar {
  visibility: hidden;
}

#items {
  overflow-y: scroll;
  flex-grow: 1;
}

#items table {
  line-height: 17px;

  /* This background image gives every other row a gray background.
   * This is simlar to "tr:nth-child(odd) background-color: #eee;".
   * However, we can't do it that way, since some rows might be hidden.
   */
  background-image: url(data:image/gif;base64,R0lGODdhAQBQAIABAO7u7v///ywAAAAAAQBQAAACC4SPqcsYD6OctMYCADs=);
  background-repeat: repeat;
}

body.dark #items table {
  background-image: url(data:image/gif;base64,R0lGODdhAQBQAIACACQkJExMTCwAAAAAAQBQAAACC4yPqcsID6OctMYCADs=);
}

#items tr {
  height: 40px;
}

#items tr[data-state="blocked"] {
  color: var(--color-brand-primary);
}

body.dark #items tr[data-state="blocked"] {
  color: #ff3a3a;
}

#items tr[data-state="allowlisted"] {
  color: #080;
}

body.dark #items tr[data-state="allowlisted"] {
  color: #389c22;
}

#items[data-filter-state="blocked"] tr:not([data-state="blocked"]),
#items[data-filter-state="allowlisted"] tr:not([data-state="allowlisted"]) {
  display: none;
}

.changed,
.unnamed {
  font-style: italic;
}

.request-wrapper,
.filter-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

tr:not(:hover) .action {
  display: none;
}

.url {
  width: 100%;
}

.url > a,
.url-rewritten > a {
  text-decoration: none;
}

.url > a:hover,
.url-rewritten > a:hover {
  text-decoration: underline;
}

.action-wrapper {
  display: flex;
  width: 100%;
}

.action {
  flex-shrink: 0;
  margin: auto;
  margin-left: 5px;
  padding: 2px 6px;
  border-radius: 7px;
  font-style: 400;
  color: #fff;
  background: #555;
  cursor: pointer;
}

.filter-wrapper,
.filter,
.origin,
.domain {
  flex-grow: 1;
}

.domain,
.origin,
.changed .request-wrapper,
.changed .filter-wrapper,
.changed .type {
  opacity: 0.6;
}

footer {
  width: 100%;
  height: 23px;
  margin-bottom: -23px;
  padding: 4px 3px;
  border-top: 1px solid #cdcdcd;
  flex-shrink: 0;
}

.has-changes + footer {
  margin-bottom: 0;
  transition: margin-bottom 0.5s;
}

footer > a {
  color: #00f;
  text-decoration: underline;
  cursor: pointer;
}

.filtered-by-search {
  display: none;
}

body.dark #reload {
  color: #2a67e7;
}
`, "",{"version":3,"sources":["webpack://./src/devtools-panel/ui/devtools-panel.css"],"names":[],"mappings":"AAAA;;;;;;;;;;;;;;;EAeE;;AAIF;EACE,sBAAsB;EACtB,2EAA2E;EAC3E,eAAe;AACjB;;AAEA;EACE,gBAAgB;EAChB,YAAY;AACd;;AAEA;EACE,cAAc;AAChB;;AAEA;EACE,aAAa;EACb,sBAAsB;EACtB,YAAY;EACZ,SAAS;EACT,cAAc;AAChB;;AAEA;EACE,iDAAiD;AACnD;;AAEA;EACE,WAAW;AACb;;AAEA;EACE,mBAAmB;EACnB,WAAW;EACX,yBAAyB;AAC3B;;AAEA;EACE,gBAAgB;EAChB,uBAAuB;AACzB;;AAEA;EACE,YAAY;EACZ,8BAA8B;EAC9B,mBAAmB;AACrB;;AAEA;EACE,uBAAuB;AACzB;;AAEA;EACE,YAAY;AACd;;AAEA;EACE,UAAU;AACZ;;AAEA;EACE,kBAAkB;EAClB,gCAAgC;EAChC,cAAc;AAChB;;AAEA;;;EAGE;AACF;EACE,kBAAkB;AACpB;;AAEA;EACE,kBAAkB;EAClB,YAAY;AACd;;AAEA;EACE,iBAAiB;;EAEjB;;;IAGE;EACF,yGAAyG;EACzG,yBAAyB;AAC3B;;AAEA;EACE,yGAAyG;AAC3G;;AAEA;EACE,YAAY;AACd;;AAEA;EACE,iCAAiC;AACnC;;AAEA;EACE,cAAc;AAChB;;AAEA;EACE,WAAW;AACb;;AAEA;EACE,cAAc;AAChB;;AAEA;;EAEE,aAAa;AACf;;AAEA;;EAEE,kBAAkB;AACpB;;AAEA;;EAEE,aAAa;EACb,sBAAsB;EACtB,YAAY;AACd;;AAEA;EACE,aAAa;AACf;;AAEA;EACE,WAAW;AACb;;AAEA;;EAEE,qBAAqB;AACvB;;AAEA;;EAEE,0BAA0B;AAC5B;;AAEA;EACE,aAAa;EACb,WAAW;AACb;;AAEA;EACE,cAAc;EACd,YAAY;EACZ,gBAAgB;EAChB,gBAAgB;EAChB,kBAAkB;EAClB,eAAe;EACf,WAAW;EACX,gBAAgB;EAChB,eAAe;AACjB;;AAEA;;;;EAIE,YAAY;AACd;;AAEA;;;;;EAKE,YAAY;AACd;;AAEA;EACE,WAAW;EACX,YAAY;EACZ,oBAAoB;EACpB,gBAAgB;EAChB,6BAA6B;EAC7B,cAAc;AAChB;;AAEA;EACE,gBAAgB;EAChB,8BAA8B;AAChC;;AAEA;EACE,WAAW;EACX,0BAA0B;EAC1B,eAAe;AACjB;;AAEA;EACE,aAAa;AACf;;AAEA;EACE,cAAc;AAChB","sourcesContent":["/*\n * This file is part of Adblock Plus <https://adblockplus.org/>,\n * Copyright (C) 2006-present eyeo GmbH\n *\n * Adblock Plus is free software: you can redistribute it and/or modify\n * it under the terms of the GNU General Public License version 3 as\n * published by the Free Software Foundation.\n *\n * Adblock Plus is distributed in the hope that it will be useful,\n * but WITHOUT ANY WARRANTY; without even the implied warranty of\n * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n * GNU General Public License for more details.\n *\n * You should have received a copy of the GNU General Public License\n * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.\n */\n\n@import \"../../theme/ui/light.css\";\n\n* {\n  box-sizing: border-box;\n  font-family: \"Lucida Grande\", \"Segoe UI\", Ubuntu, Tahoma, Arial, sans-serif;\n  font-size: 11px;\n}\n\nhtml {\n  overflow: hidden;\n  height: 100%;\n}\n\na {\n  color: inherit;\n}\n\nbody {\n  display: flex;\n  flex-direction: column;\n  height: 100%;\n  margin: 0;\n  color: #303942;\n}\n\nbody.default {\n  background-color: var(--background-color-primary);\n}\n\nbody.dark {\n  color: #fff;\n}\n\ntable {\n  table-layout: fixed;\n  width: 100%;\n  border-collapse: collapse;\n}\n\ntable * {\n  overflow: hidden;\n  text-overflow: ellipsis;\n}\n\ntd {\n  padding: 3px;\n  border-left: 1px solid #cdcdcd;\n  white-space: nowrap;\n}\n\ntd:first-child {\n  border-left-style: none;\n}\n\ncol:nth-child(2) {\n  width: 115px;\n}\n\ncol:nth-child(3) {\n  width: 50%;\n}\n\nheader {\n  overflow-y: scroll;\n  border-bottom: 1px solid #cdcdcd;\n  flex-shrink: 0;\n}\n\n/*\n * We have to add a scrollbar to the header to have the columns there aligned\n * with the table below. But we don't want the scrollbar to be visible there.\n */\nheader::-webkit-scrollbar {\n  visibility: hidden;\n}\n\n#items {\n  overflow-y: scroll;\n  flex-grow: 1;\n}\n\n#items table {\n  line-height: 17px;\n\n  /* This background image gives every other row a gray background.\n   * This is simlar to \"tr:nth-child(odd) background-color: #eee;\".\n   * However, we can't do it that way, since some rows might be hidden.\n   */\n  background-image: url(data:image/gif;base64,R0lGODdhAQBQAIABAO7u7v///ywAAAAAAQBQAAACC4SPqcsYD6OctMYCADs=);\n  background-repeat: repeat;\n}\n\nbody.dark #items table {\n  background-image: url(data:image/gif;base64,R0lGODdhAQBQAIACACQkJExMTCwAAAAAAQBQAAACC4yPqcsID6OctMYCADs=);\n}\n\n#items tr {\n  height: 40px;\n}\n\n#items tr[data-state=\"blocked\"] {\n  color: var(--color-brand-primary);\n}\n\nbody.dark #items tr[data-state=\"blocked\"] {\n  color: #ff3a3a;\n}\n\n#items tr[data-state=\"allowlisted\"] {\n  color: #080;\n}\n\nbody.dark #items tr[data-state=\"allowlisted\"] {\n  color: #389c22;\n}\n\n#items[data-filter-state=\"blocked\"] tr:not([data-state=\"blocked\"]),\n#items[data-filter-state=\"allowlisted\"] tr:not([data-state=\"allowlisted\"]) {\n  display: none;\n}\n\n.changed,\n.unnamed {\n  font-style: italic;\n}\n\n.request-wrapper,\n.filter-wrapper {\n  display: flex;\n  flex-direction: column;\n  height: 100%;\n}\n\ntr:not(:hover) .action {\n  display: none;\n}\n\n.url {\n  width: 100%;\n}\n\n.url > a,\n.url-rewritten > a {\n  text-decoration: none;\n}\n\n.url > a:hover,\n.url-rewritten > a:hover {\n  text-decoration: underline;\n}\n\n.action-wrapper {\n  display: flex;\n  width: 100%;\n}\n\n.action {\n  flex-shrink: 0;\n  margin: auto;\n  margin-left: 5px;\n  padding: 2px 6px;\n  border-radius: 7px;\n  font-style: 400;\n  color: #fff;\n  background: #555;\n  cursor: pointer;\n}\n\n.filter-wrapper,\n.filter,\n.origin,\n.domain {\n  flex-grow: 1;\n}\n\n.domain,\n.origin,\n.changed .request-wrapper,\n.changed .filter-wrapper,\n.changed .type {\n  opacity: 0.6;\n}\n\nfooter {\n  width: 100%;\n  height: 23px;\n  margin-bottom: -23px;\n  padding: 4px 3px;\n  border-top: 1px solid #cdcdcd;\n  flex-shrink: 0;\n}\n\n.has-changes + footer {\n  margin-bottom: 0;\n  transition: margin-bottom 0.5s;\n}\n\nfooter > a {\n  color: #00f;\n  text-decoration: underline;\n  cursor: pointer;\n}\n\n.filtered-by-search {\n  display: none;\n}\n\nbody.dark #reload {\n  color: #2a67e7;\n}\n"],"sourceRoot":""}]);
// Exports
/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (___CSS_LOADER_EXPORT___);


/***/ }),

/***/ 4341:
/***/ ((module, __webpack_exports__, __webpack_require__) => {

/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   A: () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(5516);
/* harmony import */ var _node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(1364);
/* harmony import */ var _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(_node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1__);
// Imports


var ___CSS_LOADER_EXPORT___ = _node_modules_css_loader_dist_runtime_api_js__WEBPACK_IMPORTED_MODULE_1___default()((_node_modules_css_loader_dist_runtime_sourceMaps_js__WEBPACK_IMPORTED_MODULE_0___default()));
// Module
___CSS_LOADER_EXPORT___.push([module.id, `/*
 * This file is part of Adblock Plus <https://adblockplus.org/>,
 * Copyright (C) 2006-present eyeo GmbH
 *
 * Adblock Plus is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Adblock Plus is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.
 */

:root {
  --background-color-cta-primary: #0797e1;
  --background-color-cta-primary-hover: #0797e1ee;
  --background-color-cta-secondary: #fff;
  --background-color-cta-secondary-hover: #0001;
  --background-color-error: #f7dde1;
  --background-color-info: #0797e1;
  --background-color-secondary: #f7f7f7;
  --background-color-primary: #fff;
  --background-color-ternary: #edf9ff;
  --border-color-cta-primary: var(--background-color-cta-primary);
  --border-color-cta-secondary: var(--color-primary);
  --border-color-secondary: #d2d2d2;
  --border-color-primary: #cdcdcd;
  --border-color-ternary: #c0e6f9;
  --border-color-outline: #acacac;
  --border-radius: 4px;
  --border-radius-primary: 6px;
  --border-style-primary: solid;
  --border-width-thick: 4px;
  --border-width-thin: 1px;
  --box-shadow-primary: 0 2px 4px 0 hsla(0, 0%, 84%, 0.5);
  --color-brand-primary: #ed1e45;
  --color-cta-primary: #fff;
  --color-cta-secondary: #666;
  --color-primary: #585858;
  --color-secondary: #000;
  --color-dimmed: #4a4a4a;
  --color-critical: var(--color-brand-primary);
  --color-default: #ff8f00;
  --color-error: var(--color-brand-primary);
  --color-link: #0797e1;
  --color-info: #0797e1;
  --color-premium: #eda51e;
  --color-premium-hover: #eb9b05;
  --font-size-heavy: 20px;
  --font-size-big: 17px;
  --font-size-medium: 16px;
  --font-size-primary: 13px;
  --font-size-small: 12px;
  --margin-primary: 16px;
  --margin-secondary: calc(var(--margin-primary) / 2);
  --padding-primary: 16px;
  --padding-secondary: calc(var(--padding-primary) / 2);
  --primary-outline: var(--border-color-outline) dotted 1px;
}
`, "",{"version":3,"sources":["webpack://./src/theme/ui/light.css"],"names":[],"mappings":"AAAA;;;;;;;;;;;;;;;EAeE;;AAEF;EACE,uCAAuC;EACvC,+CAA+C;EAC/C,sCAAsC;EACtC,6CAA6C;EAC7C,iCAAiC;EACjC,gCAAgC;EAChC,qCAAqC;EACrC,gCAAgC;EAChC,mCAAmC;EACnC,+DAA+D;EAC/D,kDAAkD;EAClD,iCAAiC;EACjC,+BAA+B;EAC/B,+BAA+B;EAC/B,+BAA+B;EAC/B,oBAAoB;EACpB,4BAA4B;EAC5B,6BAA6B;EAC7B,yBAAyB;EACzB,wBAAwB;EACxB,uDAAuD;EACvD,8BAA8B;EAC9B,yBAAyB;EACzB,2BAA2B;EAC3B,wBAAwB;EACxB,uBAAuB;EACvB,uBAAuB;EACvB,4CAA4C;EAC5C,wBAAwB;EACxB,yCAAyC;EACzC,qBAAqB;EACrB,qBAAqB;EACrB,wBAAwB;EACxB,8BAA8B;EAC9B,uBAAuB;EACvB,qBAAqB;EACrB,wBAAwB;EACxB,yBAAyB;EACzB,uBAAuB;EACvB,sBAAsB;EACtB,mDAAmD;EACnD,uBAAuB;EACvB,qDAAqD;EACrD,yDAAyD;AAC3D","sourcesContent":["/*\n * This file is part of Adblock Plus <https://adblockplus.org/>,\n * Copyright (C) 2006-present eyeo GmbH\n *\n * Adblock Plus is free software: you can redistribute it and/or modify\n * it under the terms of the GNU General Public License version 3 as\n * published by the Free Software Foundation.\n *\n * Adblock Plus is distributed in the hope that it will be useful,\n * but WITHOUT ANY WARRANTY; without even the implied warranty of\n * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n * GNU General Public License for more details.\n *\n * You should have received a copy of the GNU General Public License\n * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.\n */\n\n:root {\n  --background-color-cta-primary: #0797e1;\n  --background-color-cta-primary-hover: #0797e1ee;\n  --background-color-cta-secondary: #fff;\n  --background-color-cta-secondary-hover: #0001;\n  --background-color-error: #f7dde1;\n  --background-color-info: #0797e1;\n  --background-color-secondary: #f7f7f7;\n  --background-color-primary: #fff;\n  --background-color-ternary: #edf9ff;\n  --border-color-cta-primary: var(--background-color-cta-primary);\n  --border-color-cta-secondary: var(--color-primary);\n  --border-color-secondary: #d2d2d2;\n  --border-color-primary: #cdcdcd;\n  --border-color-ternary: #c0e6f9;\n  --border-color-outline: #acacac;\n  --border-radius: 4px;\n  --border-radius-primary: 6px;\n  --border-style-primary: solid;\n  --border-width-thick: 4px;\n  --border-width-thin: 1px;\n  --box-shadow-primary: 0 2px 4px 0 hsla(0, 0%, 84%, 0.5);\n  --color-brand-primary: #ed1e45;\n  --color-cta-primary: #fff;\n  --color-cta-secondary: #666;\n  --color-primary: #585858;\n  --color-secondary: #000;\n  --color-dimmed: #4a4a4a;\n  --color-critical: var(--color-brand-primary);\n  --color-default: #ff8f00;\n  --color-error: var(--color-brand-primary);\n  --color-link: #0797e1;\n  --color-info: #0797e1;\n  --color-premium: #eda51e;\n  --color-premium-hover: #eb9b05;\n  --font-size-heavy: 20px;\n  --font-size-big: 17px;\n  --font-size-medium: 16px;\n  --font-size-primary: 13px;\n  --font-size-small: 12px;\n  --margin-primary: 16px;\n  --margin-secondary: calc(var(--margin-primary) / 2);\n  --padding-primary: 16px;\n  --padding-secondary: calc(var(--padding-primary) / 2);\n  --primary-outline: var(--border-color-outline) dotted 1px;\n}\n"],"sourceRoot":""}]);
// Exports
/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (___CSS_LOADER_EXPORT___);


/***/ }),

/***/ 1364:
/***/ ((module) => {



/*
  MIT License http://www.opensource.org/licenses/mit-license.php
  Author Tobias Koppers @sokra
*/
module.exports = function (cssWithMappingToString) {
  var list = [];

  // return the list of modules as css string
  list.toString = function toString() {
    return this.map(function (item) {
      var content = "";
      var needLayer = typeof item[5] !== "undefined";
      if (item[4]) {
        content += "@supports (".concat(item[4], ") {");
      }
      if (item[2]) {
        content += "@media ".concat(item[2], " {");
      }
      if (needLayer) {
        content += "@layer".concat(item[5].length > 0 ? " ".concat(item[5]) : "", " {");
      }
      content += cssWithMappingToString(item);
      if (needLayer) {
        content += "}";
      }
      if (item[2]) {
        content += "}";
      }
      if (item[4]) {
        content += "}";
      }
      return content;
    }).join("");
  };

  // import a list of modules into the list
  list.i = function i(modules, media, dedupe, supports, layer) {
    if (typeof modules === "string") {
      modules = [[null, modules, undefined]];
    }
    var alreadyImportedModules = {};
    if (dedupe) {
      for (var k = 0; k < this.length; k++) {
        var id = this[k][0];
        if (id != null) {
          alreadyImportedModules[id] = true;
        }
      }
    }
    for (var _k = 0; _k < modules.length; _k++) {
      var item = [].concat(modules[_k]);
      if (dedupe && alreadyImportedModules[item[0]]) {
        continue;
      }
      if (typeof layer !== "undefined") {
        if (typeof item[5] === "undefined") {
          item[5] = layer;
        } else {
          item[1] = "@layer".concat(item[5].length > 0 ? " ".concat(item[5]) : "", " {").concat(item[1], "}");
          item[5] = layer;
        }
      }
      if (media) {
        if (!item[2]) {
          item[2] = media;
        } else {
          item[1] = "@media ".concat(item[2], " {").concat(item[1], "}");
          item[2] = media;
        }
      }
      if (supports) {
        if (!item[4]) {
          item[4] = "".concat(supports);
        } else {
          item[1] = "@supports (".concat(item[4], ") {").concat(item[1], "}");
          item[4] = supports;
        }
      }
      list.push(item);
    }
  };
  return list;
};

/***/ }),

/***/ 5516:
/***/ ((module) => {



module.exports = function (item) {
  var content = item[1];
  var cssMapping = item[3];
  if (!cssMapping) {
    return content;
  }
  if (typeof btoa === "function") {
    var base64 = btoa(unescape(encodeURIComponent(JSON.stringify(cssMapping))));
    var data = "sourceMappingURL=data:application/json;charset=utf-8;base64,".concat(base64);
    var sourceMapping = "/*# ".concat(data, " */");
    return [content].concat([sourceMapping]).join("\n");
  }
  return [content].join("\n");
};

/***/ }),

/***/ 3465:
/***/ ((module) => {



var stylesInDOM = [];
function getIndexByIdentifier(identifier) {
  var result = -1;
  for (var i = 0; i < stylesInDOM.length; i++) {
    if (stylesInDOM[i].identifier === identifier) {
      result = i;
      break;
    }
  }
  return result;
}
function modulesToDom(list, options) {
  var idCountMap = {};
  var identifiers = [];
  for (var i = 0; i < list.length; i++) {
    var item = list[i];
    var id = options.base ? item[0] + options.base : item[0];
    var count = idCountMap[id] || 0;
    var identifier = "".concat(id, " ").concat(count);
    idCountMap[id] = count + 1;
    var indexByIdentifier = getIndexByIdentifier(identifier);
    var obj = {
      css: item[1],
      media: item[2],
      sourceMap: item[3],
      supports: item[4],
      layer: item[5]
    };
    if (indexByIdentifier !== -1) {
      stylesInDOM[indexByIdentifier].references++;
      stylesInDOM[indexByIdentifier].updater(obj);
    } else {
      var updater = addElementStyle(obj, options);
      options.byIndex = i;
      stylesInDOM.splice(i, 0, {
        identifier: identifier,
        updater: updater,
        references: 1
      });
    }
    identifiers.push(identifier);
  }
  return identifiers;
}
function addElementStyle(obj, options) {
  var api = options.domAPI(options);
  api.update(obj);
  var updater = function updater(newObj) {
    if (newObj) {
      if (newObj.css === obj.css && newObj.media === obj.media && newObj.sourceMap === obj.sourceMap && newObj.supports === obj.supports && newObj.layer === obj.layer) {
        return;
      }
      api.update(obj = newObj);
    } else {
      api.remove();
    }
  };
  return updater;
}
module.exports = function (list, options) {
  options = options || {};
  list = list || [];
  var lastIdentifiers = modulesToDom(list, options);
  return function update(newList) {
    newList = newList || [];
    for (var i = 0; i < lastIdentifiers.length; i++) {
      var identifier = lastIdentifiers[i];
      var index = getIndexByIdentifier(identifier);
      stylesInDOM[index].references--;
    }
    var newLastIdentifiers = modulesToDom(newList, options);
    for (var _i = 0; _i < lastIdentifiers.length; _i++) {
      var _identifier = lastIdentifiers[_i];
      var _index = getIndexByIdentifier(_identifier);
      if (stylesInDOM[_index].references === 0) {
        stylesInDOM[_index].updater();
        stylesInDOM.splice(_index, 1);
      }
    }
    lastIdentifiers = newLastIdentifiers;
  };
};

/***/ }),

/***/ 5814:
/***/ ((module) => {



var memo = {};

/* istanbul ignore next  */
function getTarget(target) {
  if (typeof memo[target] === "undefined") {
    var styleTarget = document.querySelector(target);

    // Special case to return head of iframe instead of iframe itself
    if (window.HTMLIFrameElement && styleTarget instanceof window.HTMLIFrameElement) {
      try {
        // This will throw an exception if access to iframe is blocked
        // due to cross-origin restrictions
        styleTarget = styleTarget.contentDocument.head;
      } catch (e) {
        // istanbul ignore next
        styleTarget = null;
      }
    }
    memo[target] = styleTarget;
  }
  return memo[target];
}

/* istanbul ignore next  */
function insertBySelector(insert, style) {
  var target = getTarget(insert);
  if (!target) {
    throw new Error("Couldn't find a style target. This probably means that the value for the 'insert' parameter is invalid.");
  }
  target.appendChild(style);
}
module.exports = insertBySelector;

/***/ }),

/***/ 2389:
/***/ ((module) => {



/* istanbul ignore next  */
function insertStyleElement(options) {
  var element = document.createElement("style");
  options.setAttributes(element, options.attributes);
  options.insert(element, options.options);
  return element;
}
module.exports = insertStyleElement;

/***/ }),

/***/ 9337:
/***/ ((module, __unused_webpack_exports, __webpack_require__) => {



/* istanbul ignore next  */
function setAttributesWithoutAttributes(styleElement) {
  var nonce =  true ? __webpack_require__.nc : 0;
  if (nonce) {
    styleElement.setAttribute("nonce", nonce);
  }
}
module.exports = setAttributesWithoutAttributes;

/***/ }),

/***/ 6622:
/***/ ((module) => {



/* istanbul ignore next  */
function apply(styleElement, options, obj) {
  var css = "";
  if (obj.supports) {
    css += "@supports (".concat(obj.supports, ") {");
  }
  if (obj.media) {
    css += "@media ".concat(obj.media, " {");
  }
  var needLayer = typeof obj.layer !== "undefined";
  if (needLayer) {
    css += "@layer".concat(obj.layer.length > 0 ? " ".concat(obj.layer) : "", " {");
  }
  css += obj.css;
  if (needLayer) {
    css += "}";
  }
  if (obj.media) {
    css += "}";
  }
  if (obj.supports) {
    css += "}";
  }
  var sourceMap = obj.sourceMap;
  if (sourceMap && typeof btoa !== "undefined") {
    css += "\n/*# sourceMappingURL=data:application/json;base64,".concat(btoa(unescape(encodeURIComponent(JSON.stringify(sourceMap)))), " */");
  }

  // For old IE
  /* istanbul ignore if  */
  options.styleTagTransform(css, styleElement, options.options);
}
function removeStyleElement(styleElement) {
  // istanbul ignore if
  if (styleElement.parentNode === null) {
    return false;
  }
  styleElement.parentNode.removeChild(styleElement);
}

/* istanbul ignore next  */
function domAPI(options) {
  if (typeof document === "undefined") {
    return {
      update: function update() {},
      remove: function remove() {}
    };
  }
  var styleElement = options.insertStyleElement(options);
  return {
    update: function update(obj) {
      apply(styleElement, options, obj);
    },
    remove: function remove() {
      removeStyleElement(styleElement);
    }
  };
}
module.exports = domAPI;

/***/ }),

/***/ 8722:
/***/ ((module) => {



/* istanbul ignore next  */
function styleTagTransform(css, styleElement) {
  if (styleElement.styleSheet) {
    styleElement.styleSheet.cssText = css;
  } else {
    while (styleElement.firstChild) {
      styleElement.removeChild(styleElement.firstChild);
    }
    styleElement.appendChild(document.createTextNode(css));
  }
}
module.exports = styleTagTransform;

/***/ }),

/***/ 2558:
/***/ ((module, __unused_webpack_exports, __webpack_require__) => {

/* @@package_name - v@@version - @@timestamp */
/* -*- Mode: indent-tabs-mode: nil; js-indent-level: 2 -*- */
/* vim: set sts=2 sw=2 et tw=80: */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */


if (!(globalThis.chrome && globalThis.chrome.runtime && globalThis.chrome.runtime.id)) {
  throw new Error("This script should only be loaded in a browser extension.");
}

if (!(globalThis.browser && globalThis.browser.runtime && globalThis.browser.runtime.id)) {
  const CHROME_SEND_MESSAGE_CALLBACK_NO_RESPONSE_MESSAGE = "The message port closed before a response was received.";

  // Wrapping the bulk of this polyfill in a one-time-use function is a minor
  // optimization for Firefox. Since Spidermonkey does not fully parse the
  // contents of a function until the first time it's called, and since it will
  // never actually need to be called, this allows the polyfill to be included
  // in Firefox nearly for free.
  const wrapAPIs = extensionAPIs => {
    // NOTE: apiMetadata is associated to the content of the api-metadata.json file
    // at build time by replacing the following "include" with the content of the
    // JSON file.
    const apiMetadata = __webpack_require__(2058);

    if (Object.keys(apiMetadata).length === 0) {
      throw new Error("api-metadata.json has not been included in browser-polyfill");
    }

    /**
     * A WeakMap subclass which creates and stores a value for any key which does
     * not exist when accessed, but behaves exactly as an ordinary WeakMap
     * otherwise.
     *
     * @param {function} createItem
     *        A function which will be called in order to create the value for any
     *        key which does not exist, the first time it is accessed. The
     *        function receives, as its only argument, the key being created.
     */
    class DefaultWeakMap extends WeakMap {
      constructor(createItem, items = undefined) {
        super(items);
        this.createItem = createItem;
      }

      get(key) {
        if (!this.has(key)) {
          this.set(key, this.createItem(key));
        }

        return super.get(key);
      }
    }

    /**
     * Returns true if the given object is an object with a `then` method, and can
     * therefore be assumed to behave as a Promise.
     *
     * @param {*} value The value to test.
     * @returns {boolean} True if the value is thenable.
     */
    const isThenable = value => {
      return value && typeof value === "object" && typeof value.then === "function";
    };

    /**
     * Creates and returns a function which, when called, will resolve or reject
     * the given promise based on how it is called:
     *
     * - If, when called, `chrome.runtime.lastError` contains a non-null object,
     *   the promise is rejected with that value.
     * - If the function is called with exactly one argument, the promise is
     *   resolved to that value.
     * - Otherwise, the promise is resolved to an array containing all of the
     *   function's arguments.
     *
     * @param {object} promise
     *        An object containing the resolution and rejection functions of a
     *        promise.
     * @param {function} promise.resolve
     *        The promise's resolution function.
     * @param {function} promise.reject
     *        The promise's rejection function.
     * @param {object} metadata
     *        Metadata about the wrapped method which has created the callback.
     * @param {boolean} metadata.singleCallbackArg
     *        Whether or not the promise is resolved with only the first
     *        argument of the callback, alternatively an array of all the
     *        callback arguments is resolved. By default, if the callback
     *        function is invoked with only a single argument, that will be
     *        resolved to the promise, while all arguments will be resolved as
     *        an array if multiple are given.
     *
     * @returns {function}
     *        The generated callback function.
     */
    const makeCallback = (promise, metadata) => {
      // In case we encounter a browser error in the callback function, we don't
      // want to lose the stack trace leading up to this point. For that reason,
      // we need to instantiate the error outside the callback function.
      let error = new Error();
      return (...callbackArgs) => {
        if (extensionAPIs.runtime.lastError) {
          error.message = extensionAPIs.runtime.lastError.message;
          promise.reject(error);
        } else if (metadata.singleCallbackArg ||
                   (callbackArgs.length <= 1 && metadata.singleCallbackArg !== false)) {
          promise.resolve(callbackArgs[0]);
        } else {
          promise.resolve(callbackArgs);
        }
      };
    };

    const pluralizeArguments = (numArgs) => numArgs == 1 ? "argument" : "arguments";

    /**
     * Creates a wrapper function for a method with the given name and metadata.
     *
     * @param {string} name
     *        The name of the method which is being wrapped.
     * @param {object} metadata
     *        Metadata about the method being wrapped.
     * @param {integer} metadata.minArgs
     *        The minimum number of arguments which must be passed to the
     *        function. If called with fewer than this number of arguments, the
     *        wrapper will raise an exception.
     * @param {integer} metadata.maxArgs
     *        The maximum number of arguments which may be passed to the
     *        function. If called with more than this number of arguments, the
     *        wrapper will raise an exception.
     * @param {boolean} metadata.singleCallbackArg
     *        Whether or not the promise is resolved with only the first
     *        argument of the callback, alternatively an array of all the
     *        callback arguments is resolved. By default, if the callback
     *        function is invoked with only a single argument, that will be
     *        resolved to the promise, while all arguments will be resolved as
     *        an array if multiple are given.
     *
     * @returns {function(object, ...*)}
     *       The generated wrapper function.
     */
    const wrapAsyncFunction = (name, metadata) => {
      return function asyncFunctionWrapper(target, ...args) {
        if (args.length < metadata.minArgs) {
          throw new Error(`Expected at least ${metadata.minArgs} ${pluralizeArguments(metadata.minArgs)} for ${name}(), got ${args.length}`);
        }

        if (args.length > metadata.maxArgs) {
          throw new Error(`Expected at most ${metadata.maxArgs} ${pluralizeArguments(metadata.maxArgs)} for ${name}(), got ${args.length}`);
        }

        return new Promise((resolve, reject) => {
          if (metadata.fallbackToNoCallback) {
            // This API method has currently no callback on Chrome, but it return a promise on Firefox,
            // and so the polyfill will try to call it with a callback first, and it will fallback
            // to not passing the callback if the first call fails.
            try {
              target[name](...args, makeCallback({resolve, reject}, metadata));
            } catch (cbError) {
              console.warn(`${name} API method doesn't seem to support the callback parameter, ` +
                           "falling back to call it without a callback: ", cbError);

              target[name](...args);

              // Update the API method metadata, so that the next API calls will not try to
              // use the unsupported callback anymore.
              metadata.fallbackToNoCallback = false;
              metadata.noCallback = true;

              resolve();
            }
          } else if (metadata.noCallback) {
            target[name](...args);
            resolve();
          } else {
            target[name](...args, makeCallback({resolve, reject}, metadata));
          }
        });
      };
    };

    /**
     * Wraps an existing method of the target object, so that calls to it are
     * intercepted by the given wrapper function. The wrapper function receives,
     * as its first argument, the original `target` object, followed by each of
     * the arguments passed to the original method.
     *
     * @param {object} target
     *        The original target object that the wrapped method belongs to.
     * @param {function} method
     *        The method being wrapped. This is used as the target of the Proxy
     *        object which is created to wrap the method.
     * @param {function} wrapper
     *        The wrapper function which is called in place of a direct invocation
     *        of the wrapped method.
     *
     * @returns {Proxy<function>}
     *        A Proxy object for the given method, which invokes the given wrapper
     *        method in its place.
     */
    const wrapMethod = (target, method, wrapper) => {
      return new Proxy(method, {
        apply(targetMethod, thisObj, args) {
          return wrapper.call(thisObj, target, ...args);
        },
      });
    };

    let hasOwnProperty = Function.call.bind(Object.prototype.hasOwnProperty);

    /**
     * Wraps an object in a Proxy which intercepts and wraps certain methods
     * based on the given `wrappers` and `metadata` objects.
     *
     * @param {object} target
     *        The target object to wrap.
     *
     * @param {object} [wrappers = {}]
     *        An object tree containing wrapper functions for special cases. Any
     *        function present in this object tree is called in place of the
     *        method in the same location in the `target` object tree. These
     *        wrapper methods are invoked as described in {@see wrapMethod}.
     *
     * @param {object} [metadata = {}]
     *        An object tree containing metadata used to automatically generate
     *        Promise-based wrapper functions for asynchronous. Any function in
     *        the `target` object tree which has a corresponding metadata object
     *        in the same location in the `metadata` tree is replaced with an
     *        automatically-generated wrapper function, as described in
     *        {@see wrapAsyncFunction}
     *
     * @returns {Proxy<object>}
     */
    const wrapObject = (target, wrappers = {}, metadata = {}) => {
      let cache = Object.create(null);
      let handlers = {
        has(proxyTarget, prop) {
          return prop in target || prop in cache;
        },

        get(proxyTarget, prop, receiver) {
          if (prop in cache) {
            return cache[prop];
          }

          if (!(prop in target)) {
            return undefined;
          }

          let value = target[prop];

          if (typeof value === "function") {
            // This is a method on the underlying object. Check if we need to do
            // any wrapping.

            if (typeof wrappers[prop] === "function") {
              // We have a special-case wrapper for this method.
              value = wrapMethod(target, target[prop], wrappers[prop]);
            } else if (hasOwnProperty(metadata, prop)) {
              // This is an async method that we have metadata for. Create a
              // Promise wrapper for it.
              let wrapper = wrapAsyncFunction(prop, metadata[prop]);
              value = wrapMethod(target, target[prop], wrapper);
            } else {
              // This is a method that we don't know or care about. Return the
              // original method, bound to the underlying object.
              value = value.bind(target);
            }
          } else if (typeof value === "object" && value !== null &&
                     (hasOwnProperty(wrappers, prop) ||
                      hasOwnProperty(metadata, prop))) {
            // This is an object that we need to do some wrapping for the children
            // of. Create a sub-object wrapper for it with the appropriate child
            // metadata.
            value = wrapObject(value, wrappers[prop], metadata[prop]);
          } else if (hasOwnProperty(metadata, "*")) {
            // Wrap all properties in * namespace.
            value = wrapObject(value, wrappers[prop], metadata["*"]);
          } else {
            // We don't need to do any wrapping for this property,
            // so just forward all access to the underlying object.
            Object.defineProperty(cache, prop, {
              configurable: true,
              enumerable: true,
              get() {
                return target[prop];
              },
              set(value) {
                target[prop] = value;
              },
            });

            return value;
          }

          cache[prop] = value;
          return value;
        },

        set(proxyTarget, prop, value, receiver) {
          if (prop in cache) {
            cache[prop] = value;
          } else {
            target[prop] = value;
          }
          return true;
        },

        defineProperty(proxyTarget, prop, desc) {
          return Reflect.defineProperty(cache, prop, desc);
        },

        deleteProperty(proxyTarget, prop) {
          return Reflect.deleteProperty(cache, prop);
        },
      };

      // Per contract of the Proxy API, the "get" proxy handler must return the
      // original value of the target if that value is declared read-only and
      // non-configurable. For this reason, we create an object with the
      // prototype set to `target` instead of using `target` directly.
      // Otherwise we cannot return a custom object for APIs that
      // are declared read-only and non-configurable, such as `chrome.devtools`.
      //
      // The proxy handlers themselves will still use the original `target`
      // instead of the `proxyTarget`, so that the methods and properties are
      // dereferenced via the original targets.
      let proxyTarget = Object.create(target);
      return new Proxy(proxyTarget, handlers);
    };

    /**
     * Creates a set of wrapper functions for an event object, which handles
     * wrapping of listener functions that those messages are passed.
     *
     * A single wrapper is created for each listener function, and stored in a
     * map. Subsequent calls to `addListener`, `hasListener`, or `removeListener`
     * retrieve the original wrapper, so that  attempts to remove a
     * previously-added listener work as expected.
     *
     * @param {DefaultWeakMap<function, function>} wrapperMap
     *        A DefaultWeakMap object which will create the appropriate wrapper
     *        for a given listener function when one does not exist, and retrieve
     *        an existing one when it does.
     *
     * @returns {object}
     */
    const wrapEvent = wrapperMap => ({
      addListener(target, listener, ...args) {
        target.addListener(wrapperMap.get(listener), ...args);
      },

      hasListener(target, listener) {
        return target.hasListener(wrapperMap.get(listener));
      },

      removeListener(target, listener) {
        target.removeListener(wrapperMap.get(listener));
      },
    });

    const onRequestFinishedWrappers = new DefaultWeakMap(listener => {
      if (typeof listener !== "function") {
        return listener;
      }

      /**
       * Wraps an onRequestFinished listener function so that it will return a
       * `getContent()` property which returns a `Promise` rather than using a
       * callback API.
       *
       * @param {object} req
       *        The HAR entry object representing the network request.
       */
      return function onRequestFinished(req) {
        const wrappedReq = wrapObject(req, {} /* wrappers */, {
          getContent: {
            minArgs: 0,
            maxArgs: 0,
          },
        });
        listener(wrappedReq);
      };
    });

    const onMessageWrappers = new DefaultWeakMap(listener => {
      if (typeof listener !== "function") {
        return listener;
      }

      /**
       * Wraps a message listener function so that it may send responses based on
       * its return value, rather than by returning a sentinel value and calling a
       * callback. If the listener function returns a Promise, the response is
       * sent when the promise either resolves or rejects.
       *
       * @param {*} message
       *        The message sent by the other end of the channel.
       * @param {object} sender
       *        Details about the sender of the message.
       * @param {function(*)} sendResponse
       *        A callback which, when called with an arbitrary argument, sends
       *        that value as a response.
       * @returns {boolean}
       *        True if the wrapped listener returned a Promise, which will later
       *        yield a response. False otherwise.
       */
      return function onMessage(message, sender, sendResponse) {
        let didCallSendResponse = false;

        let wrappedSendResponse;
        let sendResponsePromise = new Promise(resolve => {
          wrappedSendResponse = function(response) {
            didCallSendResponse = true;
            resolve(response);
          };
        });

        let result;
        try {
          result = listener(message, sender, wrappedSendResponse);
        } catch (err) {
          result = Promise.reject(err);
        }

        const isResultThenable = result !== true && isThenable(result);

        // If the listener didn't returned true or a Promise, or called
        // wrappedSendResponse synchronously, we can exit earlier
        // because there will be no response sent from this listener.
        if (result !== true && !isResultThenable && !didCallSendResponse) {
          return false;
        }

        // A small helper to send the message if the promise resolves
        // and an error if the promise rejects (a wrapped sendMessage has
        // to translate the message into a resolved promise or a rejected
        // promise).
        const sendPromisedResult = (promise) => {
          promise.then(msg => {
            // send the message value.
            sendResponse(msg);
          }, error => {
            // Send a JSON representation of the error if the rejected value
            // is an instance of error, or the object itself otherwise.
            let message;
            if (error && (error instanceof Error ||
                typeof error.message === "string")) {
              message = error.message;
            } else {
              message = "An unexpected error occurred";
            }

            sendResponse({
              __mozWebExtensionPolyfillReject__: true,
              message,
            });
          }).catch(err => {
            // Print an error on the console if unable to send the response.
            console.error("Failed to send onMessage rejected reply", err);
          });
        };

        // If the listener returned a Promise, send the resolved value as a
        // result, otherwise wait the promise related to the wrappedSendResponse
        // callback to resolve and send it as a response.
        if (isResultThenable) {
          sendPromisedResult(result);
        } else {
          sendPromisedResult(sendResponsePromise);
        }

        // Let Chrome know that the listener is replying.
        return true;
      };
    });

    const wrappedSendMessageCallback = ({reject, resolve}, reply) => {
      if (extensionAPIs.runtime.lastError) {
        // Detect when none of the listeners replied to the sendMessage call and resolve
        // the promise to undefined as in Firefox.
        // See https://github.com/mozilla/webextension-polyfill/issues/130
        if (extensionAPIs.runtime.lastError.message === CHROME_SEND_MESSAGE_CALLBACK_NO_RESPONSE_MESSAGE) {
          resolve();
        } else {
          reject(new Error(extensionAPIs.runtime.lastError.message));
        }
      } else if (reply && reply.__mozWebExtensionPolyfillReject__) {
        // Convert back the JSON representation of the error into
        // an Error instance.
        reject(new Error(reply.message));
      } else {
        resolve(reply);
      }
    };

    const wrappedSendMessage = (name, metadata, apiNamespaceObj, ...args) => {
      if (args.length < metadata.minArgs) {
        throw new Error(`Expected at least ${metadata.minArgs} ${pluralizeArguments(metadata.minArgs)} for ${name}(), got ${args.length}`);
      }

      if (args.length > metadata.maxArgs) {
        throw new Error(`Expected at most ${metadata.maxArgs} ${pluralizeArguments(metadata.maxArgs)} for ${name}(), got ${args.length}`);
      }

      return new Promise((resolve, reject) => {
        const wrappedCb = wrappedSendMessageCallback.bind(null, {resolve, reject});
        args.push(wrappedCb);
        apiNamespaceObj.sendMessage(...args);
      });
    };

    const staticWrappers = {
      devtools: {
        network: {
          onRequestFinished: wrapEvent(onRequestFinishedWrappers),
        },
      },
      runtime: {
        onMessage: wrapEvent(onMessageWrappers),
        onMessageExternal: wrapEvent(onMessageWrappers),
        sendMessage: wrappedSendMessage.bind(null, "sendMessage", {minArgs: 1, maxArgs: 3}),
      },
      tabs: {
        sendMessage: wrappedSendMessage.bind(null, "sendMessage", {minArgs: 2, maxArgs: 3}),
      },
    };
    const settingMetadata = {
      clear: {minArgs: 1, maxArgs: 1},
      get: {minArgs: 1, maxArgs: 1},
      set: {minArgs: 1, maxArgs: 1},
    };
    apiMetadata.privacy = {
      network: {"*": settingMetadata},
      services: {"*": settingMetadata},
      websites: {"*": settingMetadata},
    };

    return wrapObject(extensionAPIs, staticWrappers, apiMetadata);
  };

  // The build process adds a UMD wrapper around this file, which makes the
  // `module` variable available.
  module.exports = wrapAPIs(chrome);
} else {
  module.exports = globalThis.browser;
}


/***/ }),

/***/ 2058:
/***/ ((module) => {

module.exports = /*#__PURE__*/JSON.parse('{"alarms":{"clear":{"minArgs":0,"maxArgs":1},"clearAll":{"minArgs":0,"maxArgs":0},"get":{"minArgs":0,"maxArgs":1},"getAll":{"minArgs":0,"maxArgs":0}},"bookmarks":{"create":{"minArgs":1,"maxArgs":1},"get":{"minArgs":1,"maxArgs":1},"getChildren":{"minArgs":1,"maxArgs":1},"getRecent":{"minArgs":1,"maxArgs":1},"getSubTree":{"minArgs":1,"maxArgs":1},"getTree":{"minArgs":0,"maxArgs":0},"move":{"minArgs":2,"maxArgs":2},"remove":{"minArgs":1,"maxArgs":1},"removeTree":{"minArgs":1,"maxArgs":1},"search":{"minArgs":1,"maxArgs":1},"update":{"minArgs":2,"maxArgs":2}},"browserAction":{"disable":{"minArgs":0,"maxArgs":1,"fallbackToNoCallback":true},"enable":{"minArgs":0,"maxArgs":1,"fallbackToNoCallback":true},"getBadgeBackgroundColor":{"minArgs":1,"maxArgs":1},"getBadgeText":{"minArgs":1,"maxArgs":1},"getPopup":{"minArgs":1,"maxArgs":1},"getTitle":{"minArgs":1,"maxArgs":1},"openPopup":{"minArgs":0,"maxArgs":0},"setBadgeBackgroundColor":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"setBadgeText":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"setIcon":{"minArgs":1,"maxArgs":1},"setPopup":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"setTitle":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true}},"browsingData":{"remove":{"minArgs":2,"maxArgs":2},"removeCache":{"minArgs":1,"maxArgs":1},"removeCookies":{"minArgs":1,"maxArgs":1},"removeDownloads":{"minArgs":1,"maxArgs":1},"removeFormData":{"minArgs":1,"maxArgs":1},"removeHistory":{"minArgs":1,"maxArgs":1},"removeLocalStorage":{"minArgs":1,"maxArgs":1},"removePasswords":{"minArgs":1,"maxArgs":1},"removePluginData":{"minArgs":1,"maxArgs":1},"settings":{"minArgs":0,"maxArgs":0}},"commands":{"getAll":{"minArgs":0,"maxArgs":0}},"contextMenus":{"remove":{"minArgs":1,"maxArgs":1},"removeAll":{"minArgs":0,"maxArgs":0},"update":{"minArgs":2,"maxArgs":2}},"cookies":{"get":{"minArgs":1,"maxArgs":1},"getAll":{"minArgs":1,"maxArgs":1},"getAllCookieStores":{"minArgs":0,"maxArgs":0},"remove":{"minArgs":1,"maxArgs":1},"set":{"minArgs":1,"maxArgs":1}},"devtools":{"inspectedWindow":{"eval":{"minArgs":1,"maxArgs":2,"singleCallbackArg":false}},"panels":{"create":{"minArgs":3,"maxArgs":3,"singleCallbackArg":true},"elements":{"createSidebarPane":{"minArgs":1,"maxArgs":1}}}},"downloads":{"cancel":{"minArgs":1,"maxArgs":1},"download":{"minArgs":1,"maxArgs":1},"erase":{"minArgs":1,"maxArgs":1},"getFileIcon":{"minArgs":1,"maxArgs":2},"open":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"pause":{"minArgs":1,"maxArgs":1},"removeFile":{"minArgs":1,"maxArgs":1},"resume":{"minArgs":1,"maxArgs":1},"search":{"minArgs":1,"maxArgs":1},"show":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true}},"extension":{"isAllowedFileSchemeAccess":{"minArgs":0,"maxArgs":0},"isAllowedIncognitoAccess":{"minArgs":0,"maxArgs":0}},"history":{"addUrl":{"minArgs":1,"maxArgs":1},"deleteAll":{"minArgs":0,"maxArgs":0},"deleteRange":{"minArgs":1,"maxArgs":1},"deleteUrl":{"minArgs":1,"maxArgs":1},"getVisits":{"minArgs":1,"maxArgs":1},"search":{"minArgs":1,"maxArgs":1}},"i18n":{"detectLanguage":{"minArgs":1,"maxArgs":1},"getAcceptLanguages":{"minArgs":0,"maxArgs":0}},"identity":{"launchWebAuthFlow":{"minArgs":1,"maxArgs":1}},"idle":{"queryState":{"minArgs":1,"maxArgs":1}},"management":{"get":{"minArgs":1,"maxArgs":1},"getAll":{"minArgs":0,"maxArgs":0},"getSelf":{"minArgs":0,"maxArgs":0},"setEnabled":{"minArgs":2,"maxArgs":2},"uninstallSelf":{"minArgs":0,"maxArgs":1}},"notifications":{"clear":{"minArgs":1,"maxArgs":1},"create":{"minArgs":1,"maxArgs":2},"getAll":{"minArgs":0,"maxArgs":0},"getPermissionLevel":{"minArgs":0,"maxArgs":0},"update":{"minArgs":2,"maxArgs":2}},"pageAction":{"getPopup":{"minArgs":1,"maxArgs":1},"getTitle":{"minArgs":1,"maxArgs":1},"hide":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"setIcon":{"minArgs":1,"maxArgs":1},"setPopup":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"setTitle":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true},"show":{"minArgs":1,"maxArgs":1,"fallbackToNoCallback":true}},"permissions":{"contains":{"minArgs":1,"maxArgs":1},"getAll":{"minArgs":0,"maxArgs":0},"remove":{"minArgs":1,"maxArgs":1},"request":{"minArgs":1,"maxArgs":1}},"runtime":{"getBackgroundPage":{"minArgs":0,"maxArgs":0},"getPlatformInfo":{"minArgs":0,"maxArgs":0},"openOptionsPage":{"minArgs":0,"maxArgs":0},"requestUpdateCheck":{"minArgs":0,"maxArgs":0},"sendMessage":{"minArgs":1,"maxArgs":3},"sendNativeMessage":{"minArgs":2,"maxArgs":2},"setUninstallURL":{"minArgs":1,"maxArgs":1}},"sessions":{"getDevices":{"minArgs":0,"maxArgs":1},"getRecentlyClosed":{"minArgs":0,"maxArgs":1},"restore":{"minArgs":0,"maxArgs":1}},"storage":{"local":{"clear":{"minArgs":0,"maxArgs":0},"get":{"minArgs":0,"maxArgs":1},"getBytesInUse":{"minArgs":0,"maxArgs":1},"remove":{"minArgs":1,"maxArgs":1},"set":{"minArgs":1,"maxArgs":1}},"managed":{"get":{"minArgs":0,"maxArgs":1},"getBytesInUse":{"minArgs":0,"maxArgs":1}},"sync":{"clear":{"minArgs":0,"maxArgs":0},"get":{"minArgs":0,"maxArgs":1},"getBytesInUse":{"minArgs":0,"maxArgs":1},"remove":{"minArgs":1,"maxArgs":1},"set":{"minArgs":1,"maxArgs":1}}},"tabs":{"captureVisibleTab":{"minArgs":0,"maxArgs":2},"create":{"minArgs":1,"maxArgs":1},"detectLanguage":{"minArgs":0,"maxArgs":1},"discard":{"minArgs":0,"maxArgs":1},"duplicate":{"minArgs":1,"maxArgs":1},"executeScript":{"minArgs":1,"maxArgs":2},"get":{"minArgs":1,"maxArgs":1},"getCurrent":{"minArgs":0,"maxArgs":0},"getZoom":{"minArgs":0,"maxArgs":1},"getZoomSettings":{"minArgs":0,"maxArgs":1},"goBack":{"minArgs":0,"maxArgs":1},"goForward":{"minArgs":0,"maxArgs":1},"highlight":{"minArgs":1,"maxArgs":1},"insertCSS":{"minArgs":1,"maxArgs":2},"move":{"minArgs":2,"maxArgs":2},"query":{"minArgs":1,"maxArgs":1},"reload":{"minArgs":0,"maxArgs":2},"remove":{"minArgs":1,"maxArgs":1},"removeCSS":{"minArgs":1,"maxArgs":2},"sendMessage":{"minArgs":2,"maxArgs":3},"setZoom":{"minArgs":1,"maxArgs":2},"setZoomSettings":{"minArgs":1,"maxArgs":2},"update":{"minArgs":1,"maxArgs":2}},"topSites":{"get":{"minArgs":0,"maxArgs":0}},"webNavigation":{"getAllFrames":{"minArgs":1,"maxArgs":1},"getFrame":{"minArgs":1,"maxArgs":1}},"webRequest":{"handlerBehaviorChanged":{"minArgs":0,"maxArgs":0}},"windows":{"create":{"minArgs":0,"maxArgs":1},"get":{"minArgs":1,"maxArgs":2},"getAll":{"minArgs":0,"maxArgs":1},"getCurrent":{"minArgs":0,"maxArgs":1},"getLastFocused":{"minArgs":0,"maxArgs":1},"remove":{"minArgs":1,"maxArgs":1},"update":{"minArgs":2,"maxArgs":2}}}');

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			id: moduleId,
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/compat get default export */
/******/ 	(() => {
/******/ 		// getDefaultExport function for compatibility with non-harmony modules
/******/ 		__webpack_require__.n = (module) => {
/******/ 			var getter = module && module.__esModule ?
/******/ 				() => (module['default']) :
/******/ 				() => (module);
/******/ 			__webpack_require__.d(getter, { a: getter });
/******/ 			return getter;
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			for(var key in definition) {
/******/ 				if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 					Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/nonce */
/******/ 	(() => {
/******/ 		__webpack_require__.nc = undefined;
/******/ 	})();
/******/ 	
/************************************************************************/
var __webpack_exports__ = {};

;// ./src/core/messaging/shared/emitter.ts
class MessageEmitter {
    constructor() {
        this.listeners = new Set();
    }
    addListener(listener) {
        this.listeners.add(listener);
    }
    removeListener(listener) {
        this.listeners.delete(listener);
    }
    dispatch(message, sender) {
        const results = [];
        for (const listener of this.listeners) {
            results.push(listener(message, sender));
        }
        return results;
    }
}

;// ./src/core/messaging/shared/messaging.ts
function getMessageResponse(responses) {
    for (const response of responses) {
        if (typeof response !== "undefined") {
            return response;
        }
    }
}
function isEventMessage(candidate) {
    return isMessage(candidate) && "action" in candidate && "args" in candidate;
}
function isMessage(candidate) {
    return (candidate !== null && typeof candidate === "object" && "type" in candidate);
}
function isListenMessage(candidate) {
    return isMessage(candidate) && "filter" in candidate;
}
function isPremiumActivateOptions(candidate) {
    return (candidate !== null && typeof candidate === "object" && "userId" in candidate);
}
function isPremiumSubscriptionsAddRemoveOptions(candidate) {
    return (candidate !== null &&
        typeof candidate === "object" &&
        "subscriptionType" in candidate);
}

;// ./src/core/messaging/front/messaging.ts

let port;
const connectListeners = new Set();
const disconnectListeners = new Set();
const messageListeners = new Set();
const messageEmitter = new MessageEmitter();
function addConnectListener(listener) {
    connectListeners.add(listener);
    listener();
}
function addDisconnectListener(listener) {
    disconnectListeners.add(listener);
}
function addMessageListener(listener) {
    messageListeners.add(listener);
}
const connect = () => {
    if (port) {
        return port;
    }
    try {
        port = browser.runtime.connect({ name: "ui" });
    }
    catch (ex) {
        port = null;
        disconnectListeners.forEach((listener) => {
            listener();
        });
        return port;
    }
    port.onMessage.addListener((message) => {
        if (!isMessage(message)) {
            return;
        }
        onMessage(message);
    });
    port.onDisconnect.addListener(onDisconnect);
    connectListeners.forEach((listener) => {
        listener();
    });
    return port;
};
function listen({ type, filter, ...options }) {
    addConnectListener(() => {
        if (port) {
            port.postMessage({
                type: `${type}.listen`,
                filter,
                ...options
            });
        }
    });
}
function onDisconnect() {
    port = null;
    setTimeout(() => connect(), 100);
}
function onMessage(message) {
    if (!message.type.endsWith(".respond")) {
        return;
    }
    messageListeners.forEach((listener) => {
        listener(message);
    });
}
function removeDisconnectListener(listener) {
    disconnectListeners.delete(listener);
}
function start() {
    connect();
    if (typeof browser.devtools === "undefined") {
        browser.runtime.onMessage.addListener((message, sender) => {
            if (!isMessage(message)) {
                return;
            }
            const responses = messageEmitter.dispatch(message, sender);
            const response = getMessageResponse(responses);
            if (typeof response === "undefined") {
                return;
            }
            return Promise.resolve(response);
        });
    }
}
start();

;// ./src/core/messaging/front/utils.ts
async function utils_send(sendType, options = {}) {
    const args = {
        ...options,
        type: sendType
    };
    return await browser.runtime.sendMessage(args);
}

;// ./src/core/messaging/front/category-app.ts


const platformToStore = new Map([
    ["chromium", "chrome"],
    ["edgehtml", "edge"],
    ["gecko", "firefox"]
]);
async function get(what) {
    const options = { what };
    return await utils_send("app.get", options);
}
async function getInfo() {
    var _a;
    const [application, platform] = await Promise.all([
        get("application"),
        get("platform")
    ]);
    let store;
    if (application !== "edge" && application !== "opera") {
        store = (_a = platformToStore.get(platform)) !== null && _a !== void 0 ? _a : "chrome";
    }
    else {
        store = application;
    }
    return {
        application,
        manifestVersion: browser.runtime.getManifest().manifest_version,
        platform,
        store
    };
}
function category_app_listen(filter) {
    listen({ type: "app", filter });
}
async function category_app_open(what, parameters = {}) {
    const options = { what, ...parameters };
    await utils_send("app.open", options);
}

;// ./src/core/messaging/front/category-filters.ts


async function category_filters_get() {
    return await send("filters.get");
}
function category_filters_listen(filter) {
    messaging.listen({ type: "filters", filter });
}

;// ./src/core/messaging/front/category-prefs.ts


async function category_prefs_get(key) {
    const options = { key };
    return await send("prefs.get", options);
}
function category_prefs_listen(filter) {
    messaging.listen({ type: "prefs", filter });
}

;// ./src/core/messaging/front/category-premium.ts


async function activate(userId) {
    const options = { userId };
    return await send("premium.activate", options);
}
async function add(subscriptionType) {
    const options = { subscriptionType };
    await send("premium.subscriptions.add", options);
}
async function category_premium_get() {
    return await send("premium.get");
}
async function getPremiumSubscriptionsState() {
    return await send("premium.subscriptions.getState");
}
function category_premium_listen(filter) {
    messaging.listen({ type: "premium", filter });
}
async function remove(subscriptionType) {
    const options = { subscriptionType };
    await send("premium.subscriptions.remove", options);
}

;// ./src/core/messaging/front/category-requests.ts

function category_requests_listen(filter, tabId) {
    listen({ type: "requests", filter, tabId });
}

;// ./src/core/messaging/front/category-stats.ts


async function getBlockedPerPage(tab) {
    const options = { tab };
    return await send("stats.getBlockedPerPage", options);
}
async function getBlockedTotal() {
    return await send("stats.getBlockedTotal");
}
function category_stats_listen(filter) {
    messaging.listen({ type: "stats", filter });
}

;// ./src/core/messaging/front/category-subscriptions.ts


async function category_subscriptions_add(url) {
    const options = { url };
    return await send("subscriptions.add", options);
}
async function category_subscriptions_get(options) {
    return await send("subscriptions.get", options !== null && options !== void 0 ? options : {});
}
async function getInitIssues() {
    return await send("subscriptions.getInitIssues");
}
async function getRecommendations() {
    return await send("subscriptions.getRecommendations");
}
function category_subscriptions_listen(filter) {
    messaging.listen({ type: "subscriptions", filter });
}
async function category_subscriptions_remove(url) {
    const options = { url };
    await send("subscriptions.remove", options);
}

;// ./src/core/messaging/front/index.ts



















;// ./src/filters/shared/filter.types.ts
var FilterOrigin;
(function (FilterOrigin) {
    FilterOrigin["popup"] = "popup";
    FilterOrigin["web"] = "web";
    FilterOrigin["devtools"] = "devtools";
    FilterOrigin["composer"] = "composer";
    FilterOrigin["optionsAllowlistedWebsites"] = "options-allowlisted-websites";
    FilterOrigin["optionsMobile"] = "options-mobile";
    FilterOrigin["optionsAdvanced"] = "options-advanced";
})(FilterOrigin || (FilterOrigin = {}));

;// ./src/filters/shared/index.ts


// EXTERNAL MODULE: ../../node_modules/webextension-polyfill/src/browser-polyfill.js
var browser_polyfill = __webpack_require__(2558);
var browser_polyfill_default = /*#__PURE__*/__webpack_require__.n(browser_polyfill);
;// ./src/i18n/ui/i18n.ts

const i18nAttributes = ["alt", "placeholder", "title", "value"];
function assignAction(elements, action) {
    for (const element of elements) {
        switch (typeof action) {
            case "string":
                element.href = action;
                element.target = "_blank";
                break;
            case "function":
                element.href = "#";
                element.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    action();
                });
                break;
        }
    }
}
function* getRemainingLinks(parent) {
    const links = parent.querySelectorAll("a:not([data-i18n-index])");
    for (const link of links) {
        yield link;
    }
}
function setElementLinks(idOrElement, ...actions) {
    var _a;
    const element = typeof idOrElement === "string"
        ? document.getElementById(idOrElement)
        : idOrElement;
    if (element === null) {
        return;
    }
    const remainingLinks = getRemainingLinks(element);
    for (let i = 0; i < actions.length; i++) {
        const links = element.querySelectorAll(`a[data-i18n-index='${i}']`);
        if (links.length > 0) {
            assignAction(links, actions[i]);
            continue;
        }
        const link = remainingLinks.next();
        if ((_a = link.done) !== null && _a !== void 0 ? _a : false)
            continue;
        assignAction([link.value], actions[i]);
    }
}
function stripTagsUnsafe(text) {
    return text.replace(/<\/?[^>]+>/g, "");
}
function setElementText(element, stringName, args, children = []) {
    function processString(str, currentElement) {
        const match = /^(.*?)<(a|em|slot|strong)(\d)?>(.*?)<\/\2\3>(.*)$/.exec(str);
        if (match !== null) {
            const [, before, name, index, innerText, after] = match;
            processString(before, currentElement);
            if (name === "slot") {
                const e = children[Number(index)];
                if (e !== undefined) {
                    currentElement.appendChild(e);
                }
            }
            else {
                const e = document.createElement(name);
                if (typeof index !== "undefined") {
                    e.dataset.i18nIndex = index;
                }
                processString(innerText, e);
                currentElement.appendChild(e);
            }
            processString(after, currentElement);
        }
        else
            currentElement.appendChild(document.createTextNode(str));
    }
    while (element.lastChild !== null) {
        element.removeChild(element.lastChild);
    }
    processString(browser_polyfill_default().i18n.getMessage(stringName, args !== null && args !== void 0 ? args : undefined), element);
}
function loadI18nStrings() {
    function resolveStringNames(container) {
        var _a, _b;
        if (container === null || container === undefined) {
            return;
        }
        {
            const elements = container.querySelectorAll("[data-i18n]");
            for (const element of elements) {
                const children = Array.from(element.children);
                setElementText(element, (_a = element.dataset.i18n) !== null && _a !== void 0 ? _a : "", null, children);
            }
        }
        for (const attr of i18nAttributes) {
            const elements = container.querySelectorAll(`[data-i18n-${attr}]`);
            for (const element of elements) {
                const stringName = (_b = element.getAttribute(`data-i18n-${attr}`)) !== null && _b !== void 0 ? _b : "";
                element.setAttribute(attr, browser_polyfill_default().i18n.getMessage(stringName));
            }
        }
    }
    resolveStringNames(document);
    for (const template of document.querySelectorAll("template")) {
        resolveStringNames(template.content);
    }
}
function isLocaleInfo(candidate) {
    return (candidate !== null &&
        typeof candidate === "object" &&
        "bidiDir" in candidate &&
        "locale" in candidate);
}
async function setLanguageAttributes() {
    const localeInfo = await browser_polyfill_default().runtime.sendMessage({
        type: "app.get",
        what: "localeInfo"
    });
    if (!isLocaleInfo(localeInfo)) {
        return;
    }
    document.documentElement.lang = localeInfo.locale;
    document.documentElement.dir = localeInfo.bidiDir;
}
function initI18n() {
    void setLanguageAttributes();
    loadI18nStrings();
}

;// ./src/i18n/ui/index.ts


;// ./js/pages/devtools-panel/records.mjs
/*
 * This file is part of Adblock Plus <https://adblockplus.org/>,
 * Copyright (C) 2006-present eyeo GmbH
 *
 * Adblock Plus is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Adblock Plus is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.
 */

let records = [];

function records_add(target, filter, subscriptions) {
  const changes = [];
  const newRecord = {
    filter: getFilterInfo(filter, subscriptions),
    target
  };

  let matchesAny = false;

  for (let i = 0; i < records.length; i++) {
    const oldRecord = records[i];

    const matches = hasRecord(newRecord, oldRecord);
    if (!matches) continue;

    matchesAny = true;

    // Update record without filters, if filter matches on later checks
    if (!filter) break;

    if (oldRecord.filter) continue;

    oldRecord.filter = filter;

    changes.push({
      filter: oldRecord.filter,
      index: i,
      initialize: true,
      request: oldRecord.target,
      type: "update"
    });
  }

  if (!matchesAny) {
    changes.push({
      filter: newRecord.filter,
      request: newRecord.target,
      type: "add"
    });

    records.push(newRecord);
  }

  return changes;
}

function clear() {
  records = [];
}

function getFilterInfo(filter, subscriptions) {
  if (!filter) return null;

  let userDefined = false;
  let subscriptionTitle = null;

  for (const subscription of subscriptions) {
    if (subscription.url.startsWith("~user~")) {
      userDefined = true;
      break;
    }

    subscriptionTitle = subscription.title;
    if (subscriptionTitle) break;
  }

  return {
    allowlisted:
      filter.type == "allowing" || filter.type == "elemhideexception",
    csp: filter.csp,
    selector: filter.selector,
    subscription: subscriptionTitle,
    text: filter.text,
    userDefined
  };
}

function hasRecord(newRecord, oldRecord) {
  if (oldRecord.target.url !== newRecord.target.url) return false;

  if (oldRecord.target.docDomain !== newRecord.target.docDomain) return false;

  // Ignore frame content allowlisting if there is already
  // a DOCUMENT exception which disables all means of blocking.
  if (oldRecord.target.type === "DOCUMENT") {
    if (!newRecord.target.isFrame) return false;
  } else if (oldRecord.target.type !== newRecord.target.type) {
    return false;
  }

  // Matched element hiding filters don't relate to a particular request,
  // so we have to compare the selector in order to avoid duplicates.
  if (oldRecord.filter && newRecord.filter) {
    if (oldRecord.filter.selector !== newRecord.filter.selector) return false;
  }

  // We apply multiple CSP filters to a document, but we must still remove
  // any duplicates. Two CSP filters are duplicates if both have identical
  // text.
  if (
    oldRecord.filter &&
    oldRecord.filter.csp &&
    newRecord.filter &&
    newRecord.filter.csp
  ) {
    if (oldRecord.filter.text !== newRecord.filter.text) return false;
  }

  return true;
}

const recordManager = {
  add: records_add,
  clear
};

/* harmony default export */ const devtools_panel_records = (recordManager);

// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/injectStylesIntoStyleTag.js
var injectStylesIntoStyleTag = __webpack_require__(3465);
var injectStylesIntoStyleTag_default = /*#__PURE__*/__webpack_require__.n(injectStylesIntoStyleTag);
// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/styleDomAPI.js
var styleDomAPI = __webpack_require__(6622);
var styleDomAPI_default = /*#__PURE__*/__webpack_require__.n(styleDomAPI);
// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/insertBySelector.js
var insertBySelector = __webpack_require__(5814);
var insertBySelector_default = /*#__PURE__*/__webpack_require__.n(insertBySelector);
// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/setAttributesWithoutAttributes.js
var setAttributesWithoutAttributes = __webpack_require__(9337);
var setAttributesWithoutAttributes_default = /*#__PURE__*/__webpack_require__.n(setAttributesWithoutAttributes);
// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/insertStyleElement.js
var insertStyleElement = __webpack_require__(2389);
var insertStyleElement_default = /*#__PURE__*/__webpack_require__.n(insertStyleElement);
// EXTERNAL MODULE: ../../node_modules/style-loader/dist/runtime/styleTagTransform.js
var styleTagTransform = __webpack_require__(8722);
var styleTagTransform_default = /*#__PURE__*/__webpack_require__.n(styleTagTransform);
// EXTERNAL MODULE: ./node_modules/css-loader/dist/cjs.js??ruleSet[1].rules[1].use[1]!./src/devtools-panel/ui/devtools-panel.css
var devtools_panel = __webpack_require__(9028);
;// ./src/devtools-panel/ui/devtools-panel.css

      
      
      
      
      
      
      
      
      

var options = {};

options.styleTagTransform = (styleTagTransform_default());
options.setAttributes = (setAttributesWithoutAttributes_default());

      options.insert = insertBySelector_default().bind(null, "head");
    
options.domAPI = (styleDomAPI_default());
options.insertStyleElement = (insertStyleElement_default());

var update = injectStylesIntoStyleTag_default()(devtools_panel/* default */.A, options);




       /* harmony default export */ const ui_devtools_panel = (devtools_panel/* default */.A && devtools_panel/* default */.A.locals ? devtools_panel/* default */.A.locals : undefined);

;// ./js/pages/devtools-panel/index.mjs
/*
 * This file is part of Adblock Plus <https://adblockplus.org/>,
 * Copyright (C) 2006-present eyeo GmbH
 *
 * Adblock Plus is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Adblock Plus is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.
 */








const { getMessage } = browser.i18n;

initI18n();

const onFilterChangedByRow = new WeakMap();
const promisedPlatform = get("platform");
const maxTitleLength = 1000;

let lastFilterQuery = null;

browser.runtime.sendMessage({ type: "types.get" }).then((filterTypes) => {
  const filterTypesElem = document.getElementById("filter-type");
  const filterStyleElem = document.createElement("style");
  for (const type of filterTypes) {
    filterStyleElem.innerHTML +=
      `#items[data-filter-type=${type}] tr:not([data-type=${type}])` +
      "{display: none;}";
    const optionNode = document.createElement("option");
    optionNode.appendChild(document.createTextNode(type));
    filterTypesElem.appendChild(optionNode);
  }
  document.body.appendChild(filterStyleElem);
});

function generateFilter(request, options = {}) {
  let { allowlisted = false, domainSpecific = false } = options;
  let filterText = request.url.replace(/^[\w-]+:\/+(?:www\.)?/, "||");
  const filterOptions = [];

  if (request.type == "POPUP") {
    filterOptions.push("popup");

    if (request.url == "about:blank") domainSpecific = true;
  }

  if (request.type == "CSP") filterOptions.push("csp");

  if (domainSpecific) filterOptions.push("domain=" + request.docDomain);

  if (filterOptions.length > 0) filterText += "$" + filterOptions.join(",");

  if (allowlisted) filterText = "@@" + filterText;

  return {
    allowlisted,
    subscription: null,
    text: filterText,
    userDefined: true
  };
}

function createActionButton(action, stringId, filter, callback) {
  const button = document.createElement("span");

  button.textContent = getMessage(stringId);
  button.classList.add("action");

  button.addEventListener(
    "click",
    async () => {
      await browser.runtime.sendMessage({
        type: "filters." + action,
        text: filter.text,
        origin: FilterOrigin.devtools
      });

      callback(filter);
    },
    false
  );

  return button;
}

function onUrlClick(event) {
  if (event.button != 0) return;

  // Firefox doesn't support the openResource API yet
  if (!("openResource" in browser.devtools.panels)) return;

  browser.devtools.panels.openResource(event.target.href);
  event.preventDefault();
}

function getTitleText(str) {
  return promisedPlatform.then((platform) => {
    // Firefox doesn't wrap tooltip strings without whitespace characters
    // so we have to split up the string into individual lines
    // https://bugzilla.mozilla.org/show_bug.cgi?id=805039
    if (platform === "gecko") {
      const maxLineCount = maxTitleLength / 50;

      let lines = str.match(/.{1,50}/g);
      if (lines.length > maxLineCount) {
        // Text is too long to display in full so we cut out the middle part
        lines = [
          ...lines.slice(0, maxLineCount / 2),
          "…",
          ...lines.slice(-(maxLineCount / 2))
        ];
      }

      return lines.join("\n");
    }

    if (str.length < maxTitleLength + 3) return str;

    // Text is too long to display in full so we cut out the middle part
    return [
      str.slice(0, maxTitleLength / 2),
      "…",
      str.slice(-(maxTitleLength / 2))
    ].join("\n");
  });
}

function onFilterRemoved(oldFilter) {
  const rows = document.querySelectorAll(`[data-filter="${oldFilter.text}"]`);
  for (const row of rows) {
    const onFilterChanged = onFilterChangedByRow.get(row);
    onFilterChanged(null);
  }
}

function createRow(request, filter, options = {}) {
  const { hasChanged = false, initialFilter = null } = options;
  const template = document.querySelector("template").content.firstElementChild;
  const row = document.importNode(template, true);
  row.dataset.type = request.type;
  row.classList.toggle("changed", hasChanged);

  row.querySelector(".domain").textContent = request.docDomain;
  row.querySelector(".type").textContent = request.type;

  const urlElement = row.querySelector(".url");
  const actionWrapper = row.querySelector(".action-wrapper");

  const onFilterChanged = (newFilter) => {
    const newRow = createRow(request, newFilter || initialFilter, {
      hasChanged: !!newFilter,
      initialFilter: newFilter ? initialFilter || filter : null
    });
    row.parentNode.replaceChild(newRow, row);

    const container = document.getElementById("items");
    container.classList.add("has-changes");
  };
  onFilterChangedByRow.set(row, onFilterChanged);

  if (request.url) {
    setElementText(urlElement, "devtools_request_url", [
      request.url,
      request.rewrittenUrl
    ]);

    const originalUrl = urlElement.querySelector("[data-i18n-index='0']");
    originalUrl.classList.add("url");
    getTitleText(request.url).then((title) => {
      originalUrl.setAttribute("title", title);
    });
    originalUrl.setAttribute("href", request.url);
    originalUrl.setAttribute("target", "_blank");

    if (request.type != "POPUP") {
      originalUrl.addEventListener("click", onUrlClick);
    }

    if (request.rewrittenUrl) {
      const rewrittenUrl = urlElement.querySelector("[data-i18n-index='1'");
      rewrittenUrl.classList.add("url-rewritten");
      getTitleText(request.rewrittenUrl).then((title) => {
        rewrittenUrl.setAttribute("title", title);
      });
      rewrittenUrl.setAttribute("href", request.rewrittenUrl);
      rewrittenUrl.setAttribute("target", "_blank");
      rewrittenUrl.addEventListener("click", onUrlClick);
    } else {
      urlElement.innerHTML = "";
      urlElement.appendChild(originalUrl);
    }
  } else {
    urlElement.innerHTML = "&nbsp;";
  }

  if (filter) {
    const filterElement = row.querySelector(".filter");
    const originElement = row.querySelector(".origin");

    getTitleText(filter.text).then((title) => {
      filterElement.setAttribute("title", title);
    });
    filterElement.textContent = filter.text;
    row.dataset.state = filter.allowlisted ? "allowlisted" : "blocked";
    row.dataset.filter = filter.text;

    if (filter.subscription) originElement.textContent = filter.subscription;
    else {
      if (filter.userDefined)
        originElement.textContent = getMessage("devtools_filter_origin_custom");
      else
        originElement.textContent = getMessage("devtools_filter_origin_none");

      originElement.classList.add("unnamed");
    }

    // We cannot generate allowing filters for already allowlisted requests
    // or for filters that are applied to frames
    // Additionally, we shouldn't generate allowing filters for blocking filters
    // that were created by an action button on this page while it's open,
    // because those should be removed instead to undo the action
    if (
      !filter.allowlisted &&
      request.type != "ELEMHIDE" &&
      request.type != "SNIPPET" &&
      !hasChanged
    ) {
      actionWrapper.appendChild(
        createActionButton(
          "add",
          "devtools_action_unblock",
          generateFilter(request, { allowlisted: true }),
          onFilterChanged
        )
      );
    }

    if (filter.userDefined) {
      actionWrapper.appendChild(
        createActionButton(
          "remove",
          "devtools_action_remove",
          filter,
          onFilterRemoved
        )
      );
    }
  }
  // We cannot generate blocking filters for the top-level frame
  else if (request.type !== "DOCUMENT") {
    actionWrapper.appendChild(
      createActionButton(
        "add",
        "devtools_action_block",
        generateFilter(request, { domainSpecific: request.specificOnly }),
        onFilterChanged
      )
    );
  }

  if (lastFilterQuery && shouldFilterRow(row, lastFilterQuery))
    row.classList.add("filtered-by-search");

  return row;
}

function shouldFilterRow(row, query) {
  const elementsToSearch = [
    row.getElementsByClassName("filter"),
    row.getElementsByClassName("origin"),
    row.getElementsByClassName("type"),
    row.getElementsByClassName("url")
  ];

  for (const elements of elementsToSearch) {
    for (const element of elements) {
      if (element.innerText.search(query) != -1) return false;
    }
  }
  return true;
}

function performSearch(table, query) {
  for (const row of table.rows) {
    if (shouldFilterRow(row, query)) row.classList.add("filtered-by-search");
    else row.classList.remove("filtered-by-search");
  }
}

function cancelSearch(table) {
  for (const row of table.rows) row.classList.remove("filtered-by-search");
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    const container = document.getElementById("items");
    const table = container.querySelector("tbody");

    document
      .querySelector("[data-i18n='devtools_footer'] > a")
      .addEventListener(
        "click",
        () => {
          browser.devtools.inspectedWindow.reload();
        },
        false
      );

    document.getElementById("filter-state").addEventListener(
      "change",
      (event) => {
        container.dataset.filterState = event.target.value;
      },
      false
    );

    document.getElementById("filter-type").addEventListener(
      "change",
      (event) => {
        container.dataset.filterType = event.target.value;
      },
      false
    );

    addMessageListener((message) => {
      if (message.type !== "requests.respond") return;

      switch (message.action) {
        case "hits":
          const [target, filter, subscriptions] = message.args;
          const changes = devtools_panel_records.add(target, filter, subscriptions);
          for (const change of changes) {
            switch (change.type) {
              case "add":
                const row = createRow(change.request, change.filter);
                table.appendChild(row);
                break;
              case "update":
                const oldRow = table.getElementsByTagName("tr")[change.index];
                const newRow = createRow(change.request, change.filter);
                oldRow.parentNode.replaceChild(newRow, oldRow);
                break;
            }
          }
          break;
        case "reset":
          devtools_panel_records.clear();
          table.innerHTML = "";
          container.classList.remove("has-changes");
          break;
      }
    });

    category_requests_listen(
      ["hits", "reset"],
      browser.devtools.inspectedWindow.tabId
    );

    window.addEventListener("message", (event) => {
      switch (event.data.type) {
        case "performSearch":
          performSearch(table, event.data.queryString);
          lastFilterQuery = event.data.queryString;
          break;
        case "cancelSearch":
          cancelSearch(table);
          lastFilterQuery = null;
          break;
      }
    });

    // Since Chrome 54 the themeName is accessible, for earlier versions we must
    // assume the default theme is being used.
    // https://bugs.chromium.org/p/chromium/issues/detail?id=608869
    const theme = browser.devtools.panels.themeName || "default";
    document.body.classList.add(theme);
  },
  false
);

document.body.hidden = false;

/******/ })()
;
//# sourceMappingURL=devtools-panel.js.map