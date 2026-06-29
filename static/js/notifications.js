function checkNotifications() {
    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notification");
        return;
    }

    if (Notification.permission !== "granted") {
        Notification.requestPermission();
    }

    // Interval to check every minute
    setInterval(async () => {
        try {
            // For demo, we assume the faculty is logged in and we fetch their personal schedule
            const response = await fetch('/faculty/timetable_api'); // We'll add this route
            const schedule = await response.json();
            
            const now = new Date();
            const currentDay = now.toLocaleString('en-us', {weekday: 'long'});
            
            schedule.forEach(item => {
                if (item.day === currentDay) {
                    const [startTime, endTime] = item.slot.split(' - ');
                    const [hours, minutes] = startTime.split(':').map(Number);
                    
                    const classTime = new Date();
                    classTime.setHours(hours, minutes, 0);
                    
                    const diff = classTime - now;
                    const diffMinutes = Math.floor(diff / (1000 * 60));
                    
                    if (diffMinutes === 5) {
                        new Notification("Class Reminder", {
                            body: `Your class ${item.subject} starts in 5 minutes!`,
                            icon: "/static/img/icon.png" // Optional
                        });
                    }
                }
            });
        } catch (e) {
            console.error("Error checking notifications:", e);
        }
    }, 60000);
}

checkNotifications();
