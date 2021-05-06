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
    q["year0"] = document.getElementById("year0").value;
    q["month0"] = document.getElementById("month0").value;
    q["year1"] = document.getElementById("year1").value;
    q["month1"] = document.getElementById("month1").value;
    q["category"] = document.getElementById("category-input").value;
    q["categorize"] = document.getElementById("categorize-input").checked;
    
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
        var grand_total = {};
        var report_header = document.getElementById("report-header");
        var report_table = document.getElementById("report-body");
        
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
                //[total_income, total_expense, grand_total]
                grand_total[key] = [0, 0, 0];
                
                row = report_table.insertRow(-1);
                var i;
                for (i = obj.categories.length-1;i >= 0;i--) {
                    cat = obj.categories[i];
                    if (obj.results[key].hasOwnProperty(cat[0])) {
                        row.insertCell(-1).innerHTML = 
                            obj.results[key][cat[0]][0].toFixed(2);
                        total_income[cat[0]] += obj.results[key][cat[0]][0];
                        grand_total[key][0] += obj.results[key][cat[0]][0];
                    } else {
                        row.insertCell(-1);
                    }
                }
                row.insertCell(-1).innerHTML = key;
                for (cat of obj.categories) {
                    if (obj.results[key].hasOwnProperty(cat[0])) {
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
                row.insertCell(-1).innerHTML = obj.results[key][0].toFixed(2);
                row.insertCell(-1).innerHTML = key;
                row.insertCell(-1).innerHTML = obj.results[key][1].toFixed(2);
                total_income += obj.results[key][0]
                total_expense += obj.results[key][1];
            }
            row = report_table.insertRow(-1);
            row.insertCell(-1).innerHTML = total_income.toFixed(2);
            row.insertCell(-1).innerHTML = 'المجموع';
            row.insertCell(-1).innerHTML = total_expense.toFixed(2);
            
            for (key in obj.results) {
                grand_total[key] =
                    [obj.results[key][0], obj.results[key][1], 0];
            }
        }
        
        for (key in grand_total) {
            grand_total[key][2] = grand_total[key][0] - grand_total[key][1]
        }
        generate_graph('graph_canvas', grand_total);
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

function generate_graph(obj_id, gdata) {
    var data = [];
    for (key in gdata) {
        data.push(gdata[key][0] - gdata[key][1]);
    }
    
    var graph_canvas = document.getElementById(obj_id);
    
    ymargin = 20;
    xmargin = 20;
    ylegend_margin = 60;
    xlegend_margin = 20;
    YLEGEND_SEP = 100;
    XLEGEND_SEP = 100;
    
    width = graph_canvas.width
    height = graph_canvas.height
    draw_height = height - 2 * ymargin - xlegend_margin;
    draw_width = width - 2 * xmargin - ylegend_margin;
    xlegends = data.length - 1;
    ylegends = Math.floor(draw_height / YLEGEND_SEP);
    
    ctx = graph_canvas.getContext("2d");
    ctx.font = "20px sans";
    ctx.textBaseline = "middle";
    
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, width, height);
    
    ctx.strokeStyle = "black";
    ctx.beginPath()
    ctx.moveTo(xmargin + ylegend_margin, ymargin)
    ctx.lineTo(xmargin + ylegend_margin, height - ymargin - xlegend_margin)
    ctx.lineTo(width - xmargin, height - ymargin - xlegend_margin)
    ctx.stroke()
    
    var mx = data.length;
    var mn = 1;
    var legend_px_step = draw_width / xlegends;
    
    var px = xmargin + ylegend_margin;
    var pv = mn;
    
    ctx.fillStyle = "black";
    ctx.textAlign = "center";
    while (pv <= mx) {
        var m = ctx.measureText(pv);
        ctx.fillText(pv, px, height - ymargin);
        pv = pv + 1;
        px = px + legend_px_step;
    }
    
    var mx = Math.max.apply(null, data);
    var mn = Math.min.apply(null, data);
    var legend_step = (mx - mn) / ylegends;
    var legend_px_step = draw_height / ylegends;
    
    var py = draw_height + ymargin;
    var pv = mn;
    
    ctx.textAlign = "left";
    while (pv <= mx) {
        var num = pv.toFixed(2);
        //var m = ctx.measureText(num);
        ctx.fillText(num, xmargin, py);
        pv = pv + legend_step;
        py = py - legend_px_step;
    }
    
    var c = 0;
    var x = draw_width * c / xlegends;
    var y = draw_height * (data[c] - mn) / (mx - mn);
    ctx.beginPath();
    ctx.moveTo(xmargin + ylegend_margin + x, height - ymargin - xlegend_margin - y);
    c++;
    while (c < data.length) {
        var x = draw_width * c / xlegends;
        var y = draw_height * (data[c] - mn) / (mx - mn);
        ctx.lineTo(xmargin + ylegend_margin + x, height - ymargin - xlegend_margin - y);
        c++;
    }
    ctx.stroke();
}

populate_category_select();

