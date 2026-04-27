import OrderModal from './OrderModal';
import type { OrderModalProps } from './OrderModal';

type TradeModalProps = Omit<OrderModalProps, 'side'> & {
  side?: OrderModalProps['side'];
};

export default function TradeModal({ sharesHeld = 0, side, ...rest }: TradeModalProps) {
  const defaultSide = side ?? (sharesHeld > 0 ? 'sell' : 'buy');
  return <OrderModal {...rest} sharesHeld={sharesHeld} side={defaultSide} />;
}
