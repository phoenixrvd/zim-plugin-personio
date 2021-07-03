//var start = '2021-07-03T08:00:00Z';
//var end = '2021-07-03T08:30:00Z';

var start = '/%start%/';
var end = '/%end%/';

function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function onResponseError(e) {
    alert(JSON.parse(e.message).error.message);
}

function onResponseSuccess() {
    var message = document.createElement('div');
    message.innerHTML = 'Success: ' + start + ' - ' + end;

    document.getElementById('attendance-widget').append(message);
}

function extractData(start, end) {
    const employeeId = window.REDUX_INITIAL_STATE.bladeState.dashboard.absences.employeeId;

    return {
        'id': uuidv4(),
        'start': start,
        'end': end,
        'comment': '',
        'project_id': null,
        'employee_id': employeeId,
        'activity_id': null
    }
}

window['@personio/request']
    .postJson( `/api/v1/attendances/periods`, [extractData(start, end)])
    .catch(onResponseError)
    .then(onResponseSuccess)