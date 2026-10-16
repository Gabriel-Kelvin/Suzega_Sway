# Simulation method

## Time and capacity

Time zero is Monday at 09:00. Each working day has a configured shift; Friday service capacity is reduced by learning hours. Human tasks pause at shift end and resume on the next working day. No overtime is modeled. Teams are dedicated to each stage. AI stages have two concurrent slots and run continuously except during the outage disruption.

## Workload

Each working day receives a fixed case count with uniformly random arrival times throughout the nominal shift, including Friday learning hours. Cases follow a sequential FIFO process. A configured share are complex: human service is multiplied by 1.8 and AI service by 1.2. Service durations use lognormal variation with log-space sigma 0.35 and mean multiplier one.

All strategies share the workload seed and stable case/stage random draws. No AI model participates in the simulation. Replications increment the base seed. Each arrangement is followed until every case closes, even after new arrivals stop.

## Arrangements

- **Today's process:** all stages use their human pool.
- **Accelerate with AI:** routine stages use AI; required-human stages retain their original human service time. Each AI execution has an explicitly configured probability of needing same-stage human handling.
- **Amplify people:** identical to the automated arrangement, except required-human service duration is multiplied by the assisted-review assumption. This does not establish equal accuracy, compliance, or outcome quality.

Setting assisted-review time saved to zero makes both AI arrangements identical. Increasing AI speed cannot change the all-human baseline. These counterfactuals are regression-tested.

## Disruptions

- Demand spike: double arrivals on working days nine through eleven (within the configured horizon).
- AI outage: a day-long interruption beginning at 11:00 on working day nine. Work crossing the interruption pauses and resumes; later jobs queue.
- Reviewer away: reduce each human-authority stage's team by one throughout the experiment, minimum one.
- Messier inputs: double AI escalation probability (capped below one). Escalations are modeled review effort, not measured error rates.

## Metrics

- **Turnaround and case P90:** elapsed calendar hours from arrival to closure, including off-hours and post-window drain. The comparison shows the mean of each replication's metric.
- **Backlog:** arrived but not closed at the end of the observation window. Arrivals equal completed plus backlog.
- **SLA:** fraction of all arriving cases closing within the configured elapsed-hour target.
- **Human service:** total active human service hours for all arriving cases, including drain. Excludes idle time and learning time.
- **Cost:** active service hours times assumed hourly cost plus AI executions times assumed execution cost. Excludes idle salaries, integration, infrastructure, and learning costs. It is not an ROI/payroll model.
- **Review utilization:** highest required-human stage utilization within the observation window, using calendar-adjusted capacity.
- **Clearance:** calendar days after the observation window until its final case closes.
- **Uncertainty:** P10–P90 of each metric across replications. These are simulation ranges, not confidence intervals. A mean can lie outside this range in a skewed small sample.
- **Chart and playback:** the first replication, not an average. Counters are computed from all cases at five snapshots per working day. Animated dots illustrate direction only. Waiting means a task has arrived but not started; paused tasks are not counted as actively working.

## Limits and calibration

No branching, shared workers across teams, prioritization, abandonment, adaptive learning, quality model, or inferred psychological score. Default settings illustrate a bottleneck, not a real client's operations. Collect representative arrivals, duration distributions, actual queue policies, escalation rates, staffing calendars, and quality acceptance criteria before calibrating this model. Preserve unfavorable scenarios and assess the assumptions with the people doing the work.
