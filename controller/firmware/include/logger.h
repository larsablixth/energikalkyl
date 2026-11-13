#pragma once

#include "scheduler.h"

void logger_init(void);
void logger_log(const char* level, const char* msg);
void logger_log_schedule(const DaySchedule* sched, const int* ev_slots, int n_ev_slots);
