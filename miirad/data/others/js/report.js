var grand_total = {};

function populate_category_select() {
    var xmlhttp = new XMLHttpRequest();
    var url = "_get_categories";
    
    function myFunction(arr) {
        var out = ['<option value="">اختر تصنيفا</option>'];
        var i;
        for(i = 0; i < arr.length; i++) {
            opt = '<option value="{}">{}</option>'.replace(
                '{}', arr[i]["id"]).replace('{}', arr[i]["name"]);
            out.push(opt);
        }
        document.getElementById("category-input").innerHTML = out.join("\n");
    }
    
    xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var myArr = JSON.parse(this.responseText);
            myFunction(myArr);
        }
    };
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function generate_report() {
    var q = {}
    var category_input = document.getElementById("category-input");
    
    q["year0"] = document.getElementById("year0").value;
    q["month0"] = document.getElementById("month0").value;
    q["year1"] = document.getElementById("year1").value;
    q["month1"] = document.getElementById("month1").value;
    q["category"] = category_input.value;
    q["categorize"] = document.getElementById("categorize-input").checked;
    q["gregorian"] = true;
    category_name = category_input.options[category_input.selectedIndex].text
    
    var qtext = [];
    for (key in q) {
        qtext.push(key + '=' + q[key]);
    }
    qtext = qtext.join('&');
    
    var xmlhttp = new XMLHttpRequest();
    var url = "_get_report?{}".replace("{}", qtext);
    
    function myFunction(obj) {
        var i;
        var cat;
        var total_income;
        var total_expense;
        var report_info = document.getElementById("report-info");
        var report_header = document.getElementById("report-header");
        var report_table = document.getElementById("report-body");
        
        info = "تقرير الفترة من بداية شهر {} إلى نهاية شهر {}";
        
        start_date_info = "<span class='report-date'>{}/{}</span>".
          replace('{}', q.year0).
          replace('{}', q.month0);
        if (obj.hasOwnProperty("gregorian0")) {
            start_date_info = start_date_info + "الموافق <span class='report-date'>{}/{}/{}</span>";
            start_date_info = start_date_info.
                replace('{}', obj.gregorian0[0]).
                replace('{}', obj.gregorian0[1]).
                replace('{}', obj.gregorian0[2]);
        }
        end_date_info = "<span class='report-date'>{}/{}</span>".
          replace('{}', q.year1).
          replace('{}', q.month1);
        if (obj.hasOwnProperty("gregorian1")) {
            end_date_info = end_date_info + "الموافق <span class='report-date'>{}/{}/{}</span>";
            end_date_info = end_date_info.
                replace('{}', obj.gregorian1[0]).
                replace('{}', obj.gregorian1[1]).
                replace('{}', obj.gregorian1[2]);
        }
        
        if (q.category !== "") {
            info = info + ' للتصنيف "{}"'.replace('{}', category_name);
        }
        
        report_info.innerHTML = info.replace('{}', start_date_info).
            replace('{}', end_date_info);
        
        grand_total = {};
        
        report_header.innerHTML = "";
        
        row = report_header.insertRow(-1);
        cell = row.appendChild(document.createElement('th'));
        cell.innerHTML = "الإيرادات";
        cell.colSpan = obj.categories.length;
        cell = row.appendChild(document.createElement('th'));
        cell.innerHTML = "الشهر";
        if (q["categorize"]) {
            cell.rowSpan = 2;
        }
        cell = row.appendChild(document.createElement('th'));
        cell.innerHTML = "المصاريف";
        cell.colSpan = obj.categories.length;
        row = report_header.insertRow(-1);
        
        if (q["categorize"]) {
            var last_child = null;
            for (cat of obj.categories) {
                cell = row.insertBefore(document.createElement('th'),
                    last_child);
                cell.innerHTML = cat[1];
                last_child = cell;
            }
            for (cat of obj.categories) {
                cell = row.appendChild(document.createElement('th'));
                cell.innerHTML = cat[1];
            }
        }
        
        report_table.innerHTML = "";
        if (q["categorize"]) {
            total_income = {};
            total_expense = {};
            for (i = obj.categories.length-1;i >= 0;i--) {
                cat = obj.categories[i];
                total_income[cat[0]] = 0;
            }
            for (cat of obj.categories) {
                total_expense[cat[0]] = 0;
            }
            for(key in obj.results) {
                //[total_income, total_expense]
                grand_total[key] = [0, 0];
                
                row = report_table.insertRow(-1);
                var i;
                for (i = obj.categories.length-1;i >= 0;i--) {
                    cat = obj.categories[i];
                    if (obj.results[key].hasOwnProperty(cat[0]) &&
                            obj.results[key][cat[0]][0] > 0) {
                        row.insertCell(-1).innerHTML = 
                            obj.results[key][cat[0]][0].toFixed(2);
                        total_income[cat[0]] += obj.results[key][cat[0]][0];
                        grand_total[key][0] += obj.results[key][cat[0]][0];
                    } else {
                        row.insertCell(-1);
                    }
                }
                cell = row.insertCell(-1)
                cell.innerHTML = key;
                cell.style.textAlign = "center"
                for (cat of obj.categories) {
                    if (obj.results[key].hasOwnProperty(cat[0]) &&
                            obj.results[key][cat[0]][1] > 0) {
                        row.insertCell(-1).innerHTML = 
                            obj.results[key][cat[0]][1].toFixed(2);
                        total_expense[cat[0]] += obj.results[key][cat[0]][1];
                        grand_total[key][1] += obj.results[key][cat[0]][1];
                    } else {
                        row.insertCell(-1);
                    }
                }
            }
            
            row = report_table.insertRow(-1);
            for (i = obj.categories.length-1;i >= 0;i--) {
                cat = obj.categories[i];
                row.insertCell(-1).innerHTML = total_income[cat[0]].toFixed(2);
            }
            row.insertCell(-1).innerHTML = 'المجموع';
            for (cat of obj.categories) {
                row.insertCell(-1).innerHTML = total_expense[cat[0]].toFixed(2);
            }
        } else {
            total_income = 0;
            total_expense = 0;
            for(key in obj.results) {
                row = report_table.insertRow(-1);
                if (obj.results[key][0] > 0) {
                    row.insertCell(-1).innerHTML =
                        obj.results[key][0].toFixed(2);
                } else {
                    row.insertCell(-1)
                }
                cell = row.insertCell(-1)
                cell.innerHTML = key;
                cell.style.textAlign = "center"
                if (obj.results[key][1] > 0) {
                    row.insertCell(-1).innerHTML =
                        obj.results[key][1].toFixed(2);
                } else {
                    row.insertCell(-1)
                }
                total_income += obj.results[key][0]
                total_expense += obj.results[key][1];
            }
            row = report_table.insertRow(-1);
            row.insertCell(-1).innerHTML = total_income.toFixed(2);
            row.insertCell(-1).innerHTML = 'المجموع';
            row.insertCell(-1).innerHTML = total_expense.toFixed(2);
            
            grand_total = obj.results;
        }
        
        cnvs = document.getElementById('graph_canvas');
        cnvs.width = report_table.offsetWidth;
        populate_totals_table(grand_total);
        populate_balance_labels(
            q['year0'], q['month0'], q['year1'], q['month1']);
        generate_graph(cnvs, grand_total);
    }
    
    xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var myObj = JSON.parse(this.responseText);
            myFunction(myObj);
        }
    };
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function populate_totals_table(data) {
    var total_incomes = 0;
    var total_expenses = 0;
    var grand_total;
    
    for (key in data) {
        total_incomes += data[key][0];
        total_expenses += data[key][1];
    }
    grand_total = total_incomes - total_expenses;
    
    document.getElementById("total-incomes-label").innerHTML =
        total_incomes.toFixed(2);
    document.getElementById("total-expenses-label").innerHTML =
        total_expenses.toFixed(2);
    if (grand_total < 0) {
        document.getElementById("grand-total-income-td").innerHTML = ""
        document.getElementById("grand-total-expense-td").innerHTML =
            "<label class='default-input medium-input total-field'>{}</label>".replace(
                "{}", (-grand_total).toFixed(2));
    } else {
        document.getElementById("grand-total-income-td").innerHTML =
            "<label class='default-input medium-input total-field'>{}</label>".replace(
                "{}", grand_total.toFixed(2));
        document.getElementById("grand-total-expense-td").innerHTML = ""
    }
}

function populate_balance_labels(y0, m0, y1, m1) {
    var start_xmlhttp = new XMLHttpRequest();
    var end_xmlhttp = new XMLHttpRequest();
    var start_url = "_get_balance?exclusive=1&year={}&month={}";
    var end_url = "_get_balance?year={}&month={}";
    
    if (isNaN(parseInt(y0)) || isNaN(parseInt(m0))) y0 = m0 = '0';
    if (isNaN(parseInt(y1)) || isNaN(parseInt(m1))) {
        y1 = '9999';
        m1 = '99';
    }
    
    start_url = start_url.replace('{}', y0).replace('{}', m0)
    end_url = end_url.replace('{}', y1).replace('{}', m1)
    
    
    
    function myFunction(label_id, value) {
        document.getElementById(label_id).innerHTML =
            value.toFixed(2)
    }
    
    start_xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var value = JSON.parse(this.responseText);
            myFunction("start-balance-label", value);
        }
    };
    
    start_xmlhttp.open("GET", start_url, true);
    start_xmlhttp.send();
    
    end_xmlhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var value = JSON.parse(this.responseText);
            myFunction("end-balance-label", value);
        }
    };
    
    end_xmlhttp.open("GET", end_url, true);
    end_xmlhttp.send();
}

function generate_graph(obj, data) {
    var margin = 60;
    var xlabel_clearance = 10;
    
    ctx = obj.getContext('2d');
    ctx.resetTransform();
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, obj.width, obj.height);
    
    ctx.lineWidth = 4;
    half_lw = ctx.lineWidth / 2;
    ctx.strokeStyle = 'black';
    ctx.strokeRect(half_lw, half_lw,
        obj.width - ctx.lineWidth, obj.height - ctx.lineWidth);
    
    ctx.lineWidth = 2;
    
    dw = obj.width - 2* margin - xlabel_clearance;
    dh = obj.height - 2*margin;
    dtop_left = [margin + xlabel_clearance, margin];
    dcenter = [dtop_left[0] + dw / 2, dtop_left[1] + dh / 2];
    
    ctx.translate(...dcenter);
    
    data = shorten_data(dw, dh, data, 30 * data[Object.keys(data)[0]].length, 20);
    
    var max_value = 0;
    for (key in data) {
        max_value = Math.max(max_value, data[key][0], data[key][1]);
    }
    draw_coordinates(ctx, dw, dh);
    draw_xlabels(ctx, dw, dh, margin, Object.keys(data), 30 * data[Object.keys(data)[0]].length);
    draw_ylabels(ctx, dw, dh, xlabel_clearance, max_value, 10);
    draw_bars(ctx, dw, dh, data, 30);
    document.getElementById("graph_img").src = obj.toDataURL();
}

function draw_coordinates(ctx, w, h) {
    ctx.strokeStyle = 'black';
    ctx.moveTo(-w/2, -h/2);
    ctx.lineTo(-w/2, h/2);
    ctx.lineTo(w/2, h/2);
    ctx.stroke()
}

function shorten_data(w, h, data, label_width, min_pad) {
    var min_group_width = 2 * min_pad + label_width;
    var min_count = Math.floor(w / min_group_width);
    var labels = Object.keys(data);
    var current_count = labels.length;
    if (current_count > min_count) {
        var smaller_count = min_count;
        var rm = current_count % smaller_count;
        while(smaller_count > 1 && rm != 0) {
            smaller_count--;
            rm = current_count % smaller_count;
        }
        var aggregate_count = current_count / smaller_count;
        var idx = 0;
        var new_data = {};
        var values;
        var i, j;
        while (idx < current_count) {
            values = [...data[labels[idx]]];
            for (i = 1;i < aggregate_count;i++) {
                for (j in values) {
                    values[j] += data[labels[idx+i]][j];
                }
            }
            new_data[labels[idx]] = values;
            idx += aggregate_count;
        }
        return new_data;
    } else {
        return data;
    }
}

function draw_xlabels(ctx, w, h, margin, labels, label_width=30, min_pad=undefined) {
    ctx.textAlign = 'center';
    ctx.fillStyle = 'black';
    
    var occupied_width = label_width * labels.length;
    var padding = (w - occupied_width) / 2 / labels.length;
    
    var position = -w/2 + padding + label_width / 2;
    y = h / 2 + margin / 2;
    for (label of labels) {
        ctx.fillText(label, position, y);
        position += 2 * padding + label_width;
    }
}

function draw_ylabels(ctx, w, h, clearance, max_value, steps=4) {
    var step = max_value / steps;
    ctx.textAlign = 'right';
    ctx.fillStyle = 'black';
    ctx.strokeStyle = 'black';
    
    var x = -w / 2 - clearance;
    var position = h / 2;
    var value = 0;
    var current_step = 0;
    while (current_step <= steps) {
        ctx.moveTo(-w/2, position);
        ctx.lineTo(w/2, position);
        ctx.stroke();
        ctx.fillText(value.toFixed(2), x, position);
        position -= h / steps;
        value += step;
        current_step += 1
    }
}

function draw_bars(ctx, w, h, data, bar_width=30) {
    var labels = Object.keys(data)
    var key;
    var group_width = bar_width * data[labels[0]].length;
    var occupied_width = group_width * labels.length;
    var padding = (w - occupied_width) / 2 / labels.length;
    
    var max_value = 0;
    for (key in data) {
        max_value = Math.max(max_value, data[key][0], data[key][1]);
    }
    
    bar_colors = ['blue', 'red', 'green', 'magenta', 'yellow', 'cyan'];
    ctx.fillStyle = 'red';
    ctx.strokeStyle = 'black';
    
    var idx;
    position = -w/2 + padding;
    for (key in data) {
        for (idx in data[key]) {
            value = data[key][idx];
            ctx.fillStyle = bar_colors[idx % bar_colors.length];
            ctx.fillRect(position, h/2, bar_width, -value / max_value * h);
            ctx.strokeRect(position, h/2, bar_width, -value / max_value * h);
            position += bar_width;
        }
        position += 2 * padding;
    }
}

populate_category_select();

var mselect = document.getElementById("month0");
mselect.selectedIndex = 1;
mselect = document.getElementById("month1");
mselect.selectedIndex = mselect.length - 1;
var yselect = document.getElementById("year0");
yselect.selectedIndex = yselect.length - 1;
yselect = document.getElementById("year1");
yselect.selectedIndex = yselect.length - 1;
