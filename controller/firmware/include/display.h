#pragma once

#include "scheduler.h"

void display_init(void);
void display_status(const char* line1, const char* line2,
                    const char* line3, const char* line4);
void display_schedule(const DaySchedule* sched, const int* ev_slots, int n_ev_slots);
void display_error(const char* msg);
