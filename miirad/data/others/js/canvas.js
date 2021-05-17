function randint (a, b) {
    mn = Math.min(a, b);
    mx = Math.max(a, b);
    m = mx - mn + 1;
    return Math.floor(m * Math.random()) + mn;
}

function generate_graph(obj, data) {
    var margin = 50;
    var xlabel_clearance = 10;
    
    ctx = obj.getContext('2d');
    ctx.resetTransform();
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, obj.width, obj.height);
        
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

function randomize_graph() {
    var obj = document.getElementById('graph_canvas');
    var data = {
        '1442-01': [randint(0, 100), randint(0, 100),],
        '1442-02': [randint(0, 100), randint(0, 100),],
        '1442-03': [randint(0, 100), randint(0, 100),],
        '1442-04': [randint(0, 100), randint(0, 100),],
        '1442-05': [randint(0, 100), randint(0, 100),],
        '1442-06': [randint(0, 100), randint(0, 100),],
        '1442-07': [randint(0, 100), randint(0, 100),],
        '1442-08': [randint(0, 100), randint(0, 100),],
        '1442-09': [randint(0, 100), randint(0, 100),],
        '1442-10': [randint(0, 100), randint(0, 100),],
        '1442-11': [randint(0, 100), randint(0, 100),],
        '1442-12': [randint(0, 100), randint(0, 100),],
    };
    generate_graph(obj, data);
}

randomize_graph();