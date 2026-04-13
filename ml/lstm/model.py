"""BehaviorLSTM — per-user behavioral anomaly detector.

Architecture from blueprint §7.1:
  - 2-layer LSTM, hidden=64, dropout=0.2
  - Attention over timesteps (learned weights, softmax)
  - FC head → sigmoid → anomaly score [0,1]

The attention lets the model focus on the suspicious windows (e.g. the
moment the customer hits the confirmation page while coached) rather than
averaging all 30 windows equally. Simple but effective.

Input shape:  (batch, seq_len=30, features=18)
Output shape: (batch, 1)
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class BehaviorLSTM(nn.Module):
    def __init__(
        self,
        input_size: int = 18,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            batch_first=True,
        )
        # Attention: score each timestep, softmax, weighted sum.
        self.attn_linear = nn.Linear(hidden_size, 1)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)
        # lstm_out: (batch, seq_len, hidden_size)

        # Attention weights
        attn_scores = self.attn_linear(lstm_out).squeeze(-1)  # (batch, seq_len)
        attn_weights = F.softmax(attn_scores, dim=1)  # (batch, seq_len)

        # Weighted sum of LSTM outputs
        context = torch.bmm(
            attn_weights.unsqueeze(1),  # (batch, 1, seq_len)
            lstm_out,                    # (batch, seq_len, hidden)
        ).squeeze(1)                     # (batch, hidden)

        return self.fc(context)          # (batch, 1)
